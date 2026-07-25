"""
IGS Daily Monitor — fail-closed dashboard finalizer (Schema 4.0).

Reads the structured artifacts captured by the daily email run
(the proprietary producer tree, not included in this public repo) and publishes a single strict
`latest.json` that the React dashboard consumes.

FAIL-CLOSED CONTRACT (every rule enforced here):
  * In a LIVE run a real business date is required (no silent "today"
    substitution for a stale/sample date).
  * Reject the run — and PRESERVE the previous last-known-good latest.json —
    if ANY of:
      - a required producer artifact is missing,
      - a required producer artifact has status='failed',
      - artifacts disagree on businessDate or runId (mixed run),
      - an artifact envelope is malformed,
      - the assembled payload fails strict validation,
      - the data is stale (business date older than the freshness window),
      - the strict JSON write would emit NaN/Inf.
  * A successful ZERO-ROW producer is allowed (status='success', 0 rows).
  * Write path: temp file -> strict json.load re-read (proves no NaN) ->
    os.replace to latest.json (atomic) -> dated copy.
  * On any failure the finalizer exits NON-ZERO and does NOT touch the
    existing latest.json.

This module performs NO SQL / API / email work and never reads email HTML.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import dashboard_contract as contract          # noqa: E402
import pipeline_exporter as exporter           # noqa: E402

# Producers that MUST be present & successful for a healthy live publish.
REQUIRED_PRODUCERS = ("alerts", "slippage", "stop_loss",
                      "price_cost_drift", "exposure")
# zScores is optional (derived scalars; may legitimately be absent).
OPTIONAL_PRODUCERS = ("zscores",)

ARTIFACT_FILES = {
    "alerts": "alerts.json",
    "slippage": "slippage.json",
    "stop_loss": "stop_loss.json",
    "price_cost_drift": "price_cost_drift.json",
    "exposure": "exposure.json",
    "zscores": "zscores.json",
}

DEFAULT_FRESHNESS_DAYS = 4  # business date must be within this many days


class FinalizeError(Exception):
    """Raised for any fail-closed condition."""


# --------------------------------------------------------------------------
# Artifact loading
# --------------------------------------------------------------------------
def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _validate_envelope(producer: str, env: Any, path: str) -> dict:
    if not isinstance(env, dict):
        raise FinalizeError(f"{producer}: artifact is not an object ({path})")
    for k in ("schemaVersion", "runId", "businessDate", "producer", "status"):
        if k not in env:
            raise FinalizeError(f"{producer}: artifact missing '{k}' ({path})")
    if env.get("producer") != producer:
        raise FinalizeError(
            f"{producer}: artifact producer mismatch "
            f"({env.get('producer')!r} != {producer!r})")
    if env.get("status") not in ("success", "failed"):
        raise FinalizeError(
            f"{producer}: invalid status {env.get('status')!r} ({path})")
    return env


def load_artifacts(
    date_dir: str,
    *,
    require_manifest: bool = False,
) -> tuple[dict[str, dict], dict[str, dict], Optional[dict]]:
    """Load all producer envelopes from a dated artifact directory.

    Returns (envelopes, producer_status, manifest).
      envelopes       : {producer: envelope}  (only those present)
      producer_status : {producer: ProducerStatus-dict} for ALL known producers
      manifest        : run_manifest.json contents or None
    Never returns for a hard error — raises FinalizeError instead.
    """
    if not os.path.isdir(date_dir):
        raise FinalizeError(f"artifact directory not found: {date_dir}")

    manifest = None
    man_path = os.path.join(date_dir, "run_manifest.json")
    if os.path.exists(man_path):
        try:
            manifest = _read_json(man_path)
        except Exception as e:
            raise FinalizeError(f"run_manifest.json unreadable: {e}")
    elif require_manifest:
        raise FinalizeError(f"run_manifest.json missing in {date_dir}")

    envelopes: dict[str, dict] = {}
    producer_status: dict[str, dict] = {}

    all_producers = list(REQUIRED_PRODUCERS) + list(OPTIONAL_PRODUCERS)
    for producer in all_producers:
        path = os.path.join(date_dir, ARTIFACT_FILES[producer])
        if not os.path.exists(path):
            producer_status[producer] = {
                "status": "missing", "rowCount": None,
                "capturedAt": None, "error": "artifact file not found",
            }
            continue
        try:
            env = _validate_envelope(producer, _read_json(path), path)
        except FinalizeError:
            raise
        except Exception as e:
            raise FinalizeError(f"{producer}: artifact unreadable: {e}")
        envelopes[producer] = env
        rc = None
        rcs = env.get("rowCounts") or {}
        if isinstance(rcs, dict):
            rc = rcs.get(producer)
            if rc is None and len(rcs) == 1:
                rc = list(rcs.values())[0]
        producer_status[producer] = {
            "status": env.get("status"),
            "rowCount": rc,
            "capturedAt": env.get("capturedAt"),
            "error": env.get("error"),
        }
    return envelopes, producer_status, manifest


# --------------------------------------------------------------------------
# Consistency + freshness checks
# --------------------------------------------------------------------------
def check_consistency(envelopes: dict[str, dict]) -> tuple[str, str]:
    """Ensure all present envelopes share one businessDate and one runId.

    Returns (business_date, run_id). Raises on mixed runs.
    """
    if not envelopes:
        raise FinalizeError("no producer artifacts present")
    dates = {e.get("businessDate") for e in envelopes.values()}
    rids = {e.get("runId") for e in envelopes.values()}
    if len(dates) != 1:
        raise FinalizeError(f"artifacts span multiple business dates: {sorted(dates)}")
    if len(rids) != 1:
        raise FinalizeError(f"artifacts span multiple run ids: {sorted(rids)}")
    bd = dates.pop()
    rid = rids.pop()
    if not bd:
        raise FinalizeError("artifacts have empty businessDate")
    return bd, rid


def check_required_present_and_ok(producer_status: dict[str, dict]) -> None:
    problems = []
    for p in REQUIRED_PRODUCERS:
        st = producer_status.get(p, {}).get("status")
        if st == "missing":
            problems.append(f"required producer '{p}' missing")
        elif st == "failed":
            problems.append(f"required producer '{p}' failed")
        elif st != "success":
            problems.append(f"required producer '{p}' has status {st!r}")
    if problems:
        raise FinalizeError("; ".join(problems))


def check_freshness(business_date: str, *, freshness_days: int,
                    live: bool, today: Optional[_dt.date] = None) -> None:
    """Reject stale data in live mode."""
    today = today or _dt.date.today()
    try:
        bd = _dt.date.fromisoformat(str(business_date)[:10])
    except ValueError:
        raise FinalizeError(f"businessDate not ISO date: {business_date!r}")
    if live:
        age = (today - bd).days
        if age < 0:
            raise FinalizeError(f"businessDate is in the future: {business_date}")
        if age > freshness_days:
            raise FinalizeError(
                f"data is stale: businessDate {business_date} is {age} days old "
                f"(freshness window {freshness_days}d)")


# --------------------------------------------------------------------------
# Payload assembly
# --------------------------------------------------------------------------
def _envelope_data(env: Optional[dict]) -> Any:
    if not env or env.get("status") != "success":
        return None
    return env.get("data")


def build_bundle(envelopes: dict[str, dict]) -> dict[str, Any]:
    """Map loaded artifact envelopes -> the exporter's bundle dict.

    The captured artifacts already hold list-of-record data (from
    dashboard_capture.df_to_records / clean_value), which pipeline_exporter's
    df_to_records accepts directly (it handles list[dict] as well as
    DataFrames).
    """
    alerts = _envelope_data(envelopes.get("alerts"))
    slippage = _envelope_data(envelopes.get("slippage"))
    stop_loss = _envelope_data(envelopes.get("stop_loss"))
    drift = _envelope_data(envelopes.get("price_cost_drift"))
    exposure = _envelope_data(envelopes.get("exposure"))
    zscores = _envelope_data(envelopes.get("zscores"))

    # The slippage artifact may carry either a flat summary list or a dict
    # with {summary, algos}. Support both without recomputation.
    slippage_summary: Any = slippage
    slippage_algos: Any = []
    if isinstance(slippage, dict):
        slippage_summary = slippage.get("summary")
        slippage_algos = slippage.get("algos") or []

    return {
        "slippage_summary": slippage_summary,
        "slippage_algos": slippage_algos,
        "alerts": alerts,
        "zscores": zscores if isinstance(zscores, dict) else {},
        "stop_loss": stop_loss,
        "price_cost_drift": drift,
        "exposure": exposure,
    }


def _derive_pipeline_status(producer_status: dict[str, dict]) -> str:
    req = [producer_status.get(p, {}).get("status") for p in REQUIRED_PRODUCERS]
    if any(s in ("failed", "missing") for s in req):
        return "failed"
    if all(s == "success" for s in req):
        # partial only if an OPTIONAL producer failed/missing
        opt = [producer_status.get(p, {}).get("status") for p in OPTIONAL_PRODUCERS]
        if any(s in ("failed",) for s in opt):
            return "partial"
        return "ok"
    return "failed"


def assemble_payload(
    envelopes: dict[str, dict],
    producer_status: dict[str, dict],
    *,
    business_date: str,
    run_id: str,
    mode: str,
    manifest: Optional[dict],
) -> dict:
    bundle = build_bundle(envelopes)
    entry = (manifest or {}).get("pipelineEntryPoint", "")
    input_ts = (manifest or {}).get("inputTimestamp", "")
    notes = list((manifest or {}).get("notes", []))

    payload = exporter.build_payload_from_bundle(
        bundle,
        business_date=business_date,
        mode=mode,
        pipeline_entry_point=entry,
        input_timestamp=input_ts,
        notes=notes,
    )
    # Finalizer owns the run id (shared across artifacts) + health verdict.
    payload["runId"] = run_id
    pstatus = _derive_pipeline_status(producer_status)
    now_iso = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    dh = payload["dataHealth"]
    dh["pipelineStatus"] = pstatus
    dh["producerStatus"] = producer_status
    dh["lastSuccessfulRunAt"] = now_iso if pstatus in ("ok", "partial") else None
    return payload


# --------------------------------------------------------------------------
# Atomic strict write with re-read verification
# --------------------------------------------------------------------------
def strict_publish(payload: dict, latest_path: str) -> list[str]:
    """Write payload atomically to latest_path after re-reading it to prove
    there are no NaN/Inf. Also writes a dated sibling copy. Returns paths.
    Raises FinalizeError on any problem WITHOUT touching latest_path.
    """
    problems = exporter.validate_payload(payload)
    if problems:
        raise FinalizeError("payload validation failed:\n  - " + "\n  - ".join(problems))
    # Live payloads must additionally pass the health gate.
    if contract.is_live_mode(payload):
        live_problems = contract.validate_live_health(payload)
        if live_problems:
            raise FinalizeError("live health invalid:\n  - " + "\n  - ".join(live_problems))

    d = os.path.dirname(os.path.abspath(latest_path))
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, f".tmp_latest_{os.getpid()}.json")

    # Strict write (allow_nan=False raises on any NaN/Inf).
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, allow_nan=False)
        fh.flush()
        os.fsync(fh.fileno())

    # Re-read + strict parse to PROVE the file has no NaN tokens.
    try:
        with open(tmp, "r", encoding="utf-8") as fh:
            text = fh.read()
        if "NaN" in text or "Infinity" in text:
            raise FinalizeError("temp latest.json contains NaN/Infinity tokens")
        json.loads(text)  # would raise on NaN with default parse_constant? guard below
        # json.loads accepts NaN by default; enforce rejection explicitly:
        json.loads(text, parse_constant=_reject_constant)
    except FinalizeError:
        _safe_unlink(tmp)
        raise
    except Exception as e:
        _safe_unlink(tmp)
        raise FinalizeError(f"re-read verification failed: {e}")

    written: list[str] = []
    os.replace(tmp, latest_path)  # atomic; only now do we overwrite last-good
    written.append(latest_path)

    bd = payload.get("businessDate") or _dt.date.today().isoformat()
    dated = os.path.join(d, f"dashboard_payload_{bd}.json")
    try:
        with open(dated, "w", encoding="utf-8") as fh:
            fh.write(text)
        written.append(dated)
    except Exception:
        pass  # dated copy is best-effort; latest.json already published
    return written


def _reject_constant(_x: str):
    raise FinalizeError("NaN/Infinity constant present in JSON")


def _safe_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Top-level finalize
# --------------------------------------------------------------------------
def finalize(
    *,
    date_dir: str,
    latest_path: str,
    mode: str = "artifact-live",
    live: bool = True,
    freshness_days: int = DEFAULT_FRESHNESS_DAYS,
    expected_business_date: Optional[str] = None,
    require_manifest: bool = False,
) -> dict:
    """Run the full fail-closed finalize. Returns a summary dict on success.
    Raises FinalizeError on any fail-closed condition (latest.json untouched).
    """
    if mode not in contract.SOURCE_MODES:
        raise FinalizeError(f"unknown mode {mode!r}")

    envelopes, producer_status, manifest = load_artifacts(
        date_dir, require_manifest=require_manifest)
    business_date, run_id = check_consistency(envelopes)

    if expected_business_date and business_date != expected_business_date:
        raise FinalizeError(
            f"businessDate {business_date} != expected {expected_business_date} "
            "(refusing to publish a different date)")

    check_required_present_and_ok(producer_status)
    check_freshness(business_date, freshness_days=freshness_days, live=live)

    payload = assemble_payload(
        envelopes, producer_status,
        business_date=business_date, run_id=run_id, mode=mode, manifest=manifest,
    )
    written = strict_publish(payload, latest_path)
    return {
        "businessDate": business_date,
        "runId": run_id,
        "mode": mode,
        "pipelineStatus": payload["dataHealth"]["pipelineStatus"],
        "rowCounts": payload["dataHealth"]["rowCounts"],
        "written": written,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _default_latest_path() -> str:
    repo = os.path.dirname(_HERE)
    return os.path.join(repo, "igs-daily-monitor", "public", "data", "latest.json")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Fail-closed finalizer: artifacts -> strict latest.json")
    ap.add_argument("--date-dir", required=True,
                    help="dated artifact dir, e.g. pipeline_output/2026-07-14")
    ap.add_argument("--latest", default=_default_latest_path(),
                    help="output latest.json path")
    ap.add_argument("--mode", default="artifact-live",
                    choices=list(contract.SOURCE_MODES))
    ap.add_argument("--no-live", action="store_true",
                    help="disable live freshness/required-producer strictness "
                         "(for dry-run / sample finalize)")
    ap.add_argument("--freshness-days", type=int, default=DEFAULT_FRESHNESS_DAYS)
    ap.add_argument("--expect-date", default=None,
                    help="require this exact businessDate")
    ap.add_argument("--require-manifest", action="store_true")
    args = ap.parse_args(argv)

    live = not args.no_live and args.mode in contract.LIVE_SOURCE_MODES
    try:
        summary = finalize(
            date_dir=args.date_dir,
            latest_path=args.latest,
            mode=args.mode,
            live=live,
            freshness_days=args.freshness_days,
            expected_business_date=args.expect_date,
            require_manifest=args.require_manifest,
        )
    except FinalizeError as e:
        sys.stderr.write(f"[finalize] FAIL-CLOSED: {e}\n")
        sys.stderr.write("[finalize] latest.json was NOT modified.\n")
        return 2
    except Exception as e:  # unexpected
        sys.stderr.write(f"[finalize] UNEXPECTED ERROR: {type(e).__name__}: {e}\n")
        sys.stderr.write("[finalize] latest.json was NOT modified.\n")
        return 3

    sys.stdout.write(
        f"[finalize] OK  date={summary['businessDate']} "
        f"status={summary['pipelineStatus']} "
        f"rows={summary['rowCounts']} -> {summary['written'][0]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
