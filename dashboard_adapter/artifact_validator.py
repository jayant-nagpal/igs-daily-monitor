"""
artifact_validator.py — validate a dated artifact directory (item 4 & 5).

The producer chain writes one JSON envelope per producer plus a run_manifest.
Return codes are NOT trusted: we validate the *artifacts themselves*. This
module is the single place that answers "is this run's artifact set complete,
consistent, and well-formed?" and is reused by the finalizer and by tests.

Required artifact set (item 5):
    alerts.json, slippage.json, stop_loss.json, price_cost_drift.json,
    exposure.json, zscores.json, run_manifest.json

Each producer envelope must carry: status, runId, businessDate, capturedAt,
rowCounts. All present envelopes must agree on a SINGLE runId and businessDate
(mixed runs are rejected). Never prints secrets or row values.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Producer artifacts that MUST be present (item 5). run_manifest is separate.
REQUIRED_PRODUCER_ARTIFACTS = (
    "alerts", "slippage", "stop_loss", "price_cost_drift", "exposure", "zscores",
)
ARTIFACT_FILES = {p: f"{p}.json" for p in REQUIRED_PRODUCER_ARTIFACTS}
MANIFEST_FILE = "run_manifest.json"

ENVELOPE_REQUIRED_KEYS = ("status", "runId", "businessDate", "capturedAt", "rowCounts")


@dataclass
class ArtifactReport:
    ok: bool = True
    business_date: Optional[str] = None
    run_id: Optional[str] = None
    missing: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    malformed: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    producer_status: Dict[str, str] = field(default_factory=dict)


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_dir(date_dir: str, *, require_manifest: bool = True) -> ArtifactReport:
    """Validate every required artifact in `date_dir`. Never raises for a data
    problem — accumulates into ArtifactReport.ok / .problems."""
    rep = ArtifactReport()

    if not os.path.isdir(date_dir):
        rep.ok = False
        rep.problems.append(f"artifact directory not found: {os.path.basename(date_dir)}")
        return rep

    # run_manifest presence
    man_path = os.path.join(date_dir, MANIFEST_FILE)
    if not os.path.exists(man_path):
        if require_manifest:
            rep.ok = False
            rep.missing.append(MANIFEST_FILE)
            rep.problems.append("run_manifest.json missing")
    else:
        try:
            _read_json(man_path)
        except Exception as e:
            rep.ok = False
            rep.malformed.append(MANIFEST_FILE)
            rep.problems.append(f"run_manifest.json unreadable: {type(e).__name__}")

    dates, rids = set(), set()
    for producer in REQUIRED_PRODUCER_ARTIFACTS:
        path = os.path.join(date_dir, ARTIFACT_FILES[producer])
        if not os.path.exists(path):
            rep.ok = False
            rep.missing.append(ARTIFACT_FILES[producer])
            rep.producer_status[producer] = "missing"
            continue
        try:
            env = _read_json(path)
        except Exception as e:
            rep.ok = False
            rep.malformed.append(ARTIFACT_FILES[producer])
            rep.producer_status[producer] = "malformed"
            rep.problems.append(f"{producer}: unreadable ({type(e).__name__})")
            continue
        if not isinstance(env, dict):
            rep.ok = False
            rep.malformed.append(ARTIFACT_FILES[producer])
            rep.producer_status[producer] = "malformed"
            continue
        missing_keys = [k for k in ENVELOPE_REQUIRED_KEYS if k not in env]
        if missing_keys:
            rep.ok = False
            rep.malformed.append(ARTIFACT_FILES[producer])
            rep.producer_status[producer] = "malformed"
            rep.problems.append(f"{producer}: envelope missing {missing_keys}")
            continue
        status = env.get("status")
        rep.producer_status[producer] = status
        if status == "failed":
            rep.ok = False
            rep.failed.append(producer)
        elif status != "success":
            rep.ok = False
            rep.problems.append(f"{producer}: unexpected status {status!r}")
        if env.get("businessDate"):
            dates.add(env.get("businessDate"))
        if env.get("runId"):
            rids.add(env.get("runId"))

    if len(dates) > 1:
        rep.ok = False
        rep.problems.append(f"artifacts span multiple businessDates: {sorted(dates)}")
    if len(rids) > 1:
        rep.ok = False
        rep.problems.append(f"artifacts span multiple runIds: {sorted(rids)}")
    rep.business_date = next(iter(dates)) if len(dates) == 1 else None
    rep.run_id = next(iter(rids)) if len(rids) == 1 else None
    return rep


def format_report(rep: ArtifactReport) -> str:
    lines = [f"[artifact-validator] ok={rep.ok} "
             f"date={rep.business_date} runId={rep.run_id}"]
    if rep.missing:
        lines.append("  missing   : " + ", ".join(rep.missing))
    if rep.failed:
        lines.append("  failed    : " + ", ".join(rep.failed))
    if rep.malformed:
        lines.append("  malformed : " + ", ".join(rep.malformed))
    for p in rep.problems:
        lines.append("  problem   : " + p)
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Validate a dated artifact directory.")
    ap.add_argument("--date-dir", required=True)
    ap.add_argument("--no-require-manifest", action="store_true")
    args = ap.parse_args()
    r = validate_dir(args.date_dir, require_manifest=not args.no_require_manifest)
    print(format_report(r))
    raise SystemExit(0 if r.ok else 1)
