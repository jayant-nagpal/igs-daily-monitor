"""
live_source_doctor.py — READ-ONLY live source health checks (S4, upgraded S9).

Checks each configured source INDEPENDENTLY with a short timeout and reports
PASS/FAIL plus a REDACTED error category. It never prints credentials, URLs,
query results, recipients, or sensitive rows.

CRITICAL: every DB URL / HTTP endpoint is built by the SHARED resolver
(dashboard_adapter/db_resolver.py) — the exact same code path the producer uses.
So a doctor PASS proves the producer's own configuration, not a parallel guess.

Gates (both required):
    IGS_ALLOW_LIVE=1   AND   --confirm-live

Sources checked (item 6):
    PositionsDB prod/dev/stg, warehouse, TimeSeriesDB, BackTesting, RefDB,
    SignalStore (PostgreSQL), ExecAPI, RiskAPI. RiskAPI uses its OWN creds when supplied.

Error categories (never a raw message):
    VPN_DNS | DRIVER | AUTH | CERTIFICATE | PERMISSION | QUERY | TIMEOUT |
    CONFIG | UNKNOWN

Only read-only probes are issued:
    * SQL Server / PostgreSQL : `SELECT 1`
    * ExecAPI / RiskAPI               : HTTP HEAD / tiny GET, status code only (body discarded)

Exit code: nonzero if ANY required source fails (or gates not satisfied).
Do NOT run against production until the source inventory is approved.
"""
from __future__ import annotations

import argparse
import os
import platform
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_config as lc          # noqa: E402
import db_resolver as R           # noqa: E402

DEFAULT_TIMEOUT = 15  # seconds. Long enough for a cross-region AWS RDS
# (e.g. SignalStore PG in us-east-1) reached over VPN from India, where the psycopg2
# handshake is slower than a raw psql connect. Still short enough to fail fast
# on a genuinely unreachable host. Override with --timeout N.

# Canonical resolver source names checked by the doctor.
REQUIRED_SOURCES = ("positionsdb", "warehouse", "signalstore", "execapi", "riskapi")
OPTIONAL_SOURCES = ("positionsdb_dev", "positionsdb_stg", "timeseriesdb",
                    "backtesting", "refdb")
ALL_SOURCES = REQUIRED_SOURCES + OPTIONAL_SOURCES


# ------------------------------------------------------ redacted categoriser
def _categorise(exc: Exception) -> str:
    """Map any exception to a coarse, secret-free category."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if isinstance(exc, (socket.timeout,)) or "timeout" in msg or "timed out" in msg:
        return "TIMEOUT"
    # Certificate / TLS trust problems get their own class (item 6).
    if any(k in msg for k in ("certificate", "ssl", "tls", "self-signed",
                              "self signed", "cert verify", "certificate_verify",
                              "unable to get local issuer", "ssl_error",
                              "hostname mismatch")):
        return "CERTIFICATE"
    if any(k in msg for k in ("getaddrinfo", "name or service", "dns",
                              "no route", "unreachable", "connection refused",
                              "could not connect", "network is unreachable")):
        return "VPN_DNS"
    if any(k in msg for k in ("driver", "libodbc", "im002", "data source name",
                              "module named 'pyodbc'", "module named 'psycopg2'",
                              "can't open lib", "unixodbc", "libodbc.so")):
        return "DRIVER"
    if any(k in msg for k in ("login failed", "password", "authentication",
                              "auth", "28000", "401", "kerberos")):
        return "AUTH"
    if any(k in msg for k in ("permission", "denied", "not authorized",
                              "403", "access is denied", "42000")):
        return "PERMISSION"
    if any(k in msg for k in ("syntax", "invalid object", "no such table",
                              "relation", "column", "query")):
        return "QUERY"
    if isinstance(exc, R.ResolverConfigError) or "config" in name or "config" in msg:
        return "CONFIG"
    return "UNKNOWN"


# --------------------------------------------------------------- host checks
def check_host() -> dict:
    sysname, machine = platform.system(), platform.machine()
    is_mac_arm = (sysname == "Darwin" and machine in ("arm64",))
    return {
        "name": "host-python",
        "detail": f"{sysname}/{machine} py{platform.python_version()}",
        "pass": True,  # informational; not a hard failure by itself
        "mac_arm64": is_mac_arm,
        "category": None if is_mac_arm else "CONFIG",
        "note": "" if is_mac_arm else "NOT native Darwin/arm64 (Mac M4 not confirmed)",
    }


def check_sqlserver_driver() -> dict:
    """Confirm an ODBC driver + pyodbc are available. Read-only, no connection."""
    try:
        import pyodbc  # noqa
        drivers = [d for d in pyodbc.drivers()]
        wanted = [d for d in drivers if "SQL Server" in d]
        ok = len(wanted) > 0
        return {
            "name": "sqlserver-driver",
            "pass": ok,
            "category": None if ok else "DRIVER",
            "detail": (f"{len(wanted)} SQL Server ODBC driver(s) present"
                       if ok else "no 'SQL Server' ODBC driver found"),
        }
    except Exception as e:  # pyodbc missing / libodbc absent, etc.
        return {"name": "sqlserver-driver", "pass": False,
                "category": _categorise(e), "detail": "pyodbc/ODBC not available"}


# ------------------------------------------------------------- source probes
def _probe_db(alias: str, timeout: int) -> dict:
    """Read-only SELECT 1 using the SHARED resolver's engine for `alias`."""
    try:
        engine = R.resolve_engine(alias, timeout=timeout)
    except R.ResolverConfigError as e:
        return {"pass": False, "category": "CONFIG", "detail": f"{alias} not configured"}
    except Exception as e:
        return {"pass": False, "category": _categorise(e), "detail": "engine build failed"}
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"pass": True, "category": None, "detail": "SELECT 1 OK"}
    except Exception as e:
        return {"pass": False, "category": _categorise(e),
                "detail": "read-only SELECT 1 failed"}


def _probe_http(alias: str, timeout: int) -> dict:
    """Read-only HTTP health probe using the resolver's endpoint + creds."""
    try:
        cfg = R.http_config(alias)
    except R.ResolverConfigError:
        return {"pass": False, "category": "CONFIG", "detail": f"{alias} not configured"}
    try:
        import os
        import requests
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(cfg.username, cfg.password) if cfg.username else None
        # TLS verify knob: some internal HTTPS hosts (like the SQL box) use a
        # self-signed cert. Honor a global or per-source opt-out so the health
        # probe behaves like the SQL TrustServerCertificate setting. Values:
        # "no"/"false"/"0" disable verification. Default = verify (secure).
        def _verify_flag() -> bool:
            per = os.environ.get(f"IGS_{cfg.cred_source.upper()}_VERIFY_SSL")
            glob = os.environ.get("IGS_HTTP_VERIFY_SSL")
            val = (per if per is not None else glob)
            if val is None:
                return True
            return val.strip().lower() not in ("no", "false", "0", "off")
        verify = _verify_flag()
        if not verify:
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        r = requests.head(cfg.base_url, auth=auth, timeout=timeout,
                          allow_redirects=True, verify=verify)
        if r.status_code >= 400 and r.status_code not in (404, 405):
            r = requests.get(cfg.base_url, auth=auth, timeout=timeout,
                             stream=True, verify=verify)
        code = r.status_code
        if code == 401:
            return {"pass": False, "category": "AUTH", "detail": "HTTP 401"}
        if code == 403:
            return {"pass": False, "category": "PERMISSION", "detail": "HTTP 403"}
        # 2xx/3xx = healthy. 404/405 at the base URL mean the SERVER answered
        # (it's reachable and TLS/auth are fine) but there's simply no resource
        # at the root path — that's a reachability PASS for a health probe; the
        # real API paths are exercised by the producer, not the doctor.
        if code in (200, 204, 301, 302, 404, 405):
            note = " (reachable; root has no health page)" if code == 404 else ""
            return {"pass": True, "category": None, "detail": f"HTTP {code}{note}"}
        return {"pass": False, "category": "QUERY", "detail": f"HTTP {code}"}
    except Exception as e:
        return {"pass": False, "category": _categorise(e), "detail": "HTTP probe failed"}


def probe_source(alias: str, timeout: int) -> dict:
    kind = R.SOURCE_KINDS.get(R.normalize_alias(alias))
    if kind == R.KIND_HTTP:
        return _probe_http(alias, timeout)
    return _probe_db(alias, timeout)


def run(confirm_live: bool, timeout: int, sources: list) -> int:
    # ---- gates ----
    if not lc.is_live_allowed() or not confirm_live:
        print("[doctor] REFUSED: live checks require IGS_ALLOW_LIVE=1 AND --confirm-live.")
        return 2
    try:
        env = lc.get_env(require=True)
    except lc.LiveConfigError as e:
        print(f"[doctor] REFUSED: {e}")
        return 2

    print(f"[doctor] env={env}  timeout={timeout}s  (READ-ONLY probes; shared resolver)")
    results = []

    host = check_host(); results.append(host)
    print(f"  {'PASS' if host['pass'] else 'WARN'}  host-python        "
          f"{host['detail']}  {host.get('note','')}".rstrip())
    drv = check_sqlserver_driver()
    print(f"  {'PASS' if drv['pass'] else 'FAIL'}  sqlserver-driver   "
          f"[{drv['category'] or '-'}] {drv['detail']}")

    required = set(REQUIRED_SOURCES)
    any_required_fail = False
    for src in sources:
        try:
            R.normalize_alias(src)
        except R.ResolverConfigError:
            continue
        res = probe_source(src, timeout)
        res["name"] = src
        results.append(res)
        tag = "PASS" if res["pass"] else "FAIL"
        req = "required" if src in required else "optional"
        print(f"  {tag}  {src:<16} [{res['category'] or '-'}] {res['detail']}  ({req})")
        if (not res["pass"]) and (src in required):
            any_required_fail = True

    sql_required = any(
        R.SOURCE_KINDS.get(R.normalize_alias(s)) == R.KIND_MSSQL
        for s in sources if s in required
    )
    driver_fatal = sql_required and not drv["pass"]

    ok = (not any_required_fail) and (not driver_fatal)
    print(f"[doctor] {'ALL REQUIRED SOURCES PASS' if ok else 'ONE OR MORE REQUIRED CHECKS FAILED'}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only IGS live source doctor.")
    ap.add_argument("--confirm-live", action="store_true",
                    help="Required (with IGS_ALLOW_LIVE=1) to run live probes.")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--sources", nargs="*", default=list(ALL_SOURCES),
                    help="Subset of resolver source names to check.")
    args = ap.parse_args(argv)
    return run(args.confirm_live, args.timeout, args.sources)


if __name__ == "__main__":
    raise SystemExit(main())
