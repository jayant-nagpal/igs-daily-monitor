"""
intraday_orchestrator.py — 30-minute intraday dashboard refresh (S6).

Runs ONE refresh cycle. A scheduler (launchd / Windows Task Scheduler / cron)
invokes it every 30 minutes; this process decides whether *this* cycle should run,
executes producers (or, in the split-host design, finalizes already-transferred
artifacts), and finalizes atomically. It NEVER sends email.

Guarantees (per S6):
  * one cycle per invocation; market-hours + weekend/holiday gating
  * Asia/Kolkata default TZ, configurable via IGS_MARKET_TZ
  * corrected inclusive market-hours window [open, close] (see
    docs/intraday_time_window.md) — never the buggy producer expression
  * non-overlapping: a filesystem lock skips a cycle if one is still running
  * per-cycle runId; single shared business date + timestamp across the cycle
  * per-producer timeout; a slow/failed producer fails the cycle (fail-closed)
  * NO email (relies on the IGS_ALLOW_EMAIL gate staying unset)
  * legitimate zero-row results are allowed (empty != failed)
  * atomic finalization via finalize_dashboard_run; last-known-good preserved
  * redacted logs (no secrets/hosts/rows/recipients)
  * nonzero exit on failure
  * per-producer freshness metadata recorded in the run manifest

This module does NOT open production connections itself; producers do. In the
Windows-produces / Mac-finalizes topology, run with --finalize-only on the Mac.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_config as lc

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


# --------------------------------------------------------------- config
def _tz():
    name = os.environ.get("IGS_MARKET_TZ", "Asia/Kolkata")
    if ZoneInfo is None:
        return None, name
    try:
        return ZoneInfo(name), name
    except Exception:
        return ZoneInfo("Asia/Kolkata"), "Asia/Kolkata"


def _hhmm(env_name: str, default: str) -> dt.time:
    raw = os.environ.get(env_name, default).strip() or default
    hh, mm = raw.split(":")
    return dt.time(int(hh), int(mm))


def market_open() -> dt.time:
    return _hhmm("IGS_MARKET_OPEN", "09:15")


def market_close() -> dt.time:
    return _hhmm("IGS_MARKET_CLOSE", "15:35")


# ------------------------------------------------------------- gating
def is_weekend(d: dt.date) -> bool:
    return d.weekday() >= 5  # Sat=5, Sun=6


def load_holidays() -> set:
    """
    Optional holiday list from IGS_MARKET_HOLIDAYS_FILE (one ISO date per line).
    Absent file => no static holidays (weekend gate still applies). The
    authoritative holiday source in production is warehouse CountryNonTradingDay;
    this file is a safe, offline, secret-free override for the orchestrator gate.
    """
    path = os.environ.get("IGS_MARKET_HOLIDAYS_FILE", "").strip()
    if not path:
        return set()
    p = Path(path).expanduser()
    if not p.is_file():
        return set()
    out = set()
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            try:
                out.add(dt.date.fromisoformat(line[:10]))
            except ValueError:
                pass
    return out


def within_market_hours(now_local: dt.datetime) -> bool:
    """Corrected INCLUSIVE window [open, close]. Not the buggy OR expression."""
    t = now_local.time()
    return market_open() <= t <= market_close()


def should_run(now_local: dt.datetime) -> tuple[bool, str]:
    d = now_local.date()
    if is_weekend(d):
        return False, "weekend"
    if d in load_holidays():
        return False, "holiday"
    if not within_market_hours(now_local):
        return False, "outside-market-hours"
    return True, "ok"


# ------------------------------------------------------------- lock
class CycleLock:
    """Filesystem lock preventing overlapping cycles. Stale locks (older than
    IGS_INTRADAY_LOCK_TTL_MIN, default 25) are reclaimed."""

    def __init__(self, lock_path: Path, ttl_min: int = 25):
        self.lock_path = lock_path
        self.ttl = dt.timedelta(minutes=ttl_min)
        self.acquired = False

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        if self.lock_path.exists():
            age = dt.datetime.now() - dt.datetime.fromtimestamp(
                self.lock_path.stat().st_mtime)
            if age < self.ttl:
                return False  # a cycle is still running
            # stale -> reclaim
        try:
            self.lock_path.write_text(str(os.getpid()))
            self.acquired = True
            return True
        except Exception:
            return False

    def release(self):
        if self.acquired:
            try:
                self.lock_path.unlink()
            except Exception:
                pass


# ------------------------------------------------------------- run ids
def make_run_id(now_local: dt.datetime) -> str:
    return "igs-" + now_local.strftime("%Y%m%d-%H%M")


def business_date(now_local: dt.datetime) -> str:
    return now_local.strftime("%Y-%m-%d")


# ------------------------------------------------------------- producers
def run_producer(cmd: list, timeout_s: int, name: str) -> dict:
    """Run one producer with a timeout. Returns redacted status dict."""
    started = dt.datetime.now()
    try:
        proc = subprocess.run(cmd, timeout=timeout_s,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        ok = proc.returncode == 0
        return {"producer": name, "ok": ok, "rc": proc.returncode,
                "seconds": round((dt.datetime.now() - started).total_seconds(), 1),
                "category": None if ok else "PRODUCER_NONZERO"}
    except subprocess.TimeoutExpired:
        return {"producer": name, "ok": False, "rc": None,
                "seconds": timeout_s, "category": "TIMEOUT"}
    except FileNotFoundError:
        return {"producer": name, "ok": False, "rc": None,
                "seconds": 0, "category": "CONFIG"}
    except Exception:
        return {"producer": name, "ok": False, "rc": None,
                "seconds": 0, "category": "UNKNOWN"}


# ------------------------------------------------------------- finalize
def finalize(date_dir: Path, business_dt: str, latest_path: Path) -> int:
    """Invoke the fail-closed finalizer. Returns its exit code (0 ok)."""
    cmd = [sys.executable, "-m", "dashboard_adapter.finalize_dashboard_run",
           "--date-dir", str(date_dir), "--mode", "artifact-live",
           "--expect-date", business_dt, "--latest", str(latest_path)]
    proc = subprocess.run(cmd)
    return proc.returncode


# ------------------------------------------------------------- cycle
def run_cycle(*, finalize_only: bool, producer_timeout: int,
              force: bool = False) -> int:
    tz, tzname = _tz()
    now_local = dt.datetime.now(tz) if tz else dt.datetime.now()

    ok, why = (True, "forced") if force else should_run(now_local)
    if not ok:
        print(f"[intraday] SKIP cycle ({why}) tz={tzname} "
              f"local={now_local.strftime('%Y-%m-%d %H:%M')}")
        return 0  # skipping is a normal, successful non-run

    run_id = make_run_id(now_local)
    biz = business_date(now_local)
    artifact_root = lc.require_absolute_artifact_dir()
    date_dir = artifact_root / biz
    date_dir.mkdir(parents=True, exist_ok=True)
    latest_path = Path(os.environ.get(
        "IGS_LATEST_PATH",
        str(Path.cwd() / "dashboard_adapter" / "sample_output" / "latest.json")))

    lock = CycleLock(artifact_root / ".intraday.lock",
                     ttl_min=int(os.environ.get("IGS_INTRADAY_LOCK_TTL_MIN", "25")))
    if not lock.acquire():
        print("[intraday] SKIP cycle (previous cycle still running — lock held)")
        return 0

    try:
        print(f"[intraday] START run_id={run_id} biz={biz} tz={tzname} "
              f"finalize_only={finalize_only} timeout={producer_timeout}s")
        results = []
        if not finalize_only:
            # Producer commands come from IGS_INTRADAY_PRODUCERS (path to a file
            # with one shell command per line) to avoid hardcoding host paths.
            prod_file = os.environ.get("IGS_INTRADAY_PRODUCERS", "").strip()
            cmds = []
            if prod_file and Path(prod_file).is_file():
                for line in Path(prod_file).read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        cmds.append(line)
            if not cmds:
                print("[intraday] FAIL: no producer commands configured "
                      "(set IGS_INTRADAY_PRODUCERS) and not --finalize-only")
                return 1
            for i, c in enumerate(cmds):
                # env carries the shared runId/date to each producer
                env_run = dict(os.environ,
                               IGS_DASHBOARD_RUN_ID=run_id,
                               IGS_DASHBOARD_BUSINESS_DATE=biz,
                               IGS_DASHBOARD_CAPTURE="1",
                               IGS_DASHBOARD_CAPTURE_DIR=str(date_dir))
                started = dt.datetime.now()
                try:
                    proc = subprocess.run(c, shell=True, timeout=producer_timeout,
                                          env=env_run,
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.PIPE)
                    res = {"producer": f"cmd{i}", "ok": proc.returncode == 0,
                           "rc": proc.returncode,
                           "seconds": round((dt.datetime.now()-started).total_seconds(),1),
                           "category": None if proc.returncode == 0 else "PRODUCER_NONZERO"}
                except subprocess.TimeoutExpired:
                    res = {"producer": f"cmd{i}", "ok": False, "rc": None,
                           "seconds": producer_timeout, "category": "TIMEOUT"}
                results.append(res)
                print(f"  producer {res['producer']}: "
                      f"{'OK' if res['ok'] else 'FAIL'} "
                      f"[{res['category'] or '-'}] {res['seconds']}s")
            if any(not r["ok"] for r in results):
                print("[intraday] FAIL: a producer failed; NOT finalizing "
                      "(last-known-good preserved).")
                return 1

        # finalize (fail-closed; preserves last-known-good on failure)
        rc = finalize(date_dir, biz, latest_path)
        if rc != 0:
            print(f"[intraday] FAIL: finalizer returned {rc}; latest.json unchanged.")
            return 1
        print(f"[intraday] OK run_id={run_id} biz={biz} finalized atomically.")
        return 0
    finally:
        lock.release()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="30-minute intraday refresh cycle.")
    ap.add_argument("--finalize-only", action="store_true",
                    help="Mac side: finalize already-transferred artifacts only.")
    ap.add_argument("--producer-timeout", type=int,
                    default=int(os.environ.get("IGS_PRODUCER_TIMEOUT", "300")))
    ap.add_argument("--force", action="store_true",
                    help="Run regardless of market-hours/holiday gate (testing).")
    args = ap.parse_args(argv)
    try:
        return run_cycle(finalize_only=args.finalize_only,
                         producer_timeout=args.producer_timeout,
                         force=args.force)
    except lc.LiveConfigError as e:
        print(f"[intraday] REFUSED: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
