"""
IGS Daily Monitor — canonical dashboard data contract (Schema 4.0).

Single source of truth for the JSON payload the React dashboard consumes
(`dashboard_data/latest.json`). Mirrors `igs-daily-monitor/src/types/dashboard.ts`.

This module is PURE: it declares the schema, the typed row shapes, empty
constructors, and a lightweight structural validator. It performs NO I/O,
NO SQL, NO API calls, and never touches email HTML / bodies / screenshots.

Design rules honoured here:
  * Derived metrics only (counts / sums / averages / max / min / top-N /
    bottom-N / abs-value ranking). No invented financial metrics.
  * Numbers are plain floats/ints or None. No NaN / Inf allowed downstream
    (see pipeline_exporter.sanitize_payload / validate_payload).

Schema 4.0 changes (additive; all 3.0 business-data row shapes preserved
byte-for-byte — no field renamed, removed, reordered, or reinterpreted):
  * dataHealth.pipelineStatus: 'ok' | 'partial' | 'failed' | 'stale'
  * dataHealth.producerStatus: typed map producer -> {status, rowCount,
    capturedAt, error}
  * dataHealth.lastSuccessfulRunAt: ISO-8601 str or None
  * source.mode gains 'artifact-live' (DEFAULT production) and 'direct-live'
    (optional explicit in-memory mode). 'pipeline-live', 'pipeline-dry-run',
    and 'sample' are retained for compatibility / non-production use.

For a 4.0 *live* payload the health fields MUST be present and valid — they
are not merely optional. Legacy 3.0 snapshots may be read only through the
explicit compatibility adapter (`adapt_legacy_v3`), which never fakes
pipelineStatus='ok' and always attaches a legacy/stale warning.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

SCHEMA_VERSION = "4.0"
SCHEMA_VERSION_LEGACY = "3.0"

# Canonical algo naming (from slippage_calc.algo_id_map).
ALGO_ID_MAP: dict[int, str] = {24: "ALGO-A", 85: "ALGO-B", 187: "ALGO-B2"}

# Allowed source modes.
#   artifact-live   -> DEFAULT production: finalize structured artifacts
#                      captured by the same daily email run (no recompute).
#   direct-live     -> optional explicit mode: in-memory ReportBundle handed
#                      straight from the email calc (needs live gates).
#   pipeline-live   -> retained legacy production label (compat).
#   pipeline-dry-run-> fixtures exercised through the real export path.
#   sample          -> built-in demo dataset.
SOURCE_MODES = (
    "artifact-live",
    "direct-live",
    "pipeline-live",
    "pipeline-dry-run",
    "sample",
)

# Modes that represent real production data and therefore REQUIRE fully
# populated + validated health fields.
LIVE_SOURCE_MODES = ("artifact-live", "direct-live", "pipeline-live")

# Pipeline health states.
PIPELINE_STATUSES = ("ok", "partial", "failed", "stale")

# Producer-level statuses. 'unknown' is reserved for the legacy-3.0 compat
# adapter — it must never be emitted by a real 4.0 writer.
PRODUCER_STATUSES = ("success", "failed", "missing", "stale", "unknown")

# Top-level report sections used for dataHealth presence tracking.
SECTIONS = (
    "slippageSummary",
    "slippageAlgos",
    "alerts",
    "stopLossWatch",
    "priceCostDrift",
    "exposure",
    "zScores",
)

# Canonical producer keys (align with dashboard_capture artifact filenames).
PRODUCERS = (
    "alerts",
    "slippage",
    "stop_loss",
    "price_cost_drift",
    "exposure",
    "zscores",
)


# --------------------------------------------------------------------------
# Row shapes (mirror dashboard.ts). Keys are the exact JSON field names.
# *** PRESERVED VERBATIM FROM SCHEMA 3.0 — DO NOT MODIFY. ***
# --------------------------------------------------------------------------
@dataclass
class SlippageSummary:
    algoId: Optional[int] = None
    algoName: str = ""
    slippageModelIgsPct: Optional[float] = None
    slippageClosePricePct: Optional[float] = None
    cumulativeDailyClosePct: Optional[float] = None
    cumulativeModelClosePct: Optional[float] = None
    todayClosePnl: Optional[float] = None
    todayModelPnl: Optional[float] = None
    cumulativeDailyClosePnl: Optional[float] = None
    cumulativeModelPnl: Optional[float] = None


@dataclass
class SlippageStock:
    algoName: str = ""
    rankType: str = "best"  # 'best' | 'worst'
    symbol: str = ""
    name: str = ""
    slippagePnlRs: Optional[float] = None
    slippagePct: Optional[float] = None


@dataclass
class SlippageHeadline:
    metric: str = ""
    slippagePct: Optional[float] = None
    pnlRs: Optional[float] = None


@dataclass
class SlippageAlgo:
    algoId: Optional[int] = None
    algoName: str = ""
    headlines: list[dict] = field(default_factory=list)
    bestStocks: list[dict] = field(default_factory=list)
    worstStocks: list[dict] = field(default_factory=list)
    dateSeries: list[dict] = field(default_factory=list)


@dataclass
class AlertRow:
    alertType: str = ""
    metric: str = ""
    currentValue: str = ""
    threshold: str = ""
    breach: str = "—"  # 'Yes' | 'No' | '—'
    actionRequired: str = ""
    severity: str = "info"  # 'ok' | 'warning' | 'breach' | 'info'


@dataclass
class StopLossWatch:
    symbol: str = ""
    name: str = ""
    resetPrice: Optional[float] = None
    lastPrice: Optional[float] = None
    chgPct: Optional[float] = None
    daysHeld: Optional[int] = None
    execWeightPct: Optional[float] = None
    pctChangePct: Optional[float] = None
    slHit: bool = False


@dataclass
class PriceCostDriftRow:
    algoName: str = ""  # 'ALGO-A' | 'ALGO-B' | 'ALGO-B2'
    symbol: str = ""
    name: str = ""
    resetPrice: Optional[float] = None
    avgCost: Optional[float] = None
    diffResetPriceAvgPricePct: float = 0.0
    execWeightPct: Optional[float] = None
    gainLossPct: Optional[float] = None


@dataclass
class ExposureRow:
    algoName: str = ""
    osid: Optional[int] = None
    quantity: Optional[float] = None
    avgPrice: Optional[float] = None
    marketPrice: Optional[float] = None
    isin: str = ""
    execWeightPct: Optional[float] = None
    gainLossPct: Optional[float] = None
    marketValue: Optional[float] = None
    symbol: str = ""
    coname: str = ""


# --------------------------------------------------------------------------
# Health shapes (NEW in 4.0)
# --------------------------------------------------------------------------
@dataclass
class ProducerStatus:
    """Per-producer health captured during the daily run."""
    status: str = "unknown"  # one of PRODUCER_STATUSES
    rowCount: Optional[int] = None
    capturedAt: Optional[str] = None  # ISO-8601
    error: Optional[str] = None


def empty_data_health() -> dict[str, Any]:
    """Return an empty-but-well-formed 4.0 dataHealth block."""
    return {
        "strictJson": True,
        "pipelineStatus": "failed",   # fail-closed default until proven ok
        "producerStatus": {},          # producer -> ProducerStatus dict
        "lastSuccessfulRunAt": None,
        "sectionsPresent": [],
        "sectionsMissing": [],
        "warnings": [],
        "rowCounts": {},
    }


# --------------------------------------------------------------------------
# Envelope
# --------------------------------------------------------------------------
def empty_payload(
    business_date: str,
    *,
    mode: str = "sample",
    run_id: str = "",
    generated_at: str = "",
    pipeline_entry_point: str = "",
    input_timestamp: str = "",
) -> dict[str, Any]:
    """Return a fully-formed, empty-but-valid 4.0 payload skeleton."""
    if mode not in SOURCE_MODES:
        raise ValueError(f"mode must be one of {SOURCE_MODES}, got {mode!r}")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runId": run_id,
        "businessDate": business_date,
        "generatedAt": generated_at,
        "source": {
            "mode": mode,
            "pipelineEntryPoint": pipeline_entry_point,
            "inputTimestamp": input_timestamp,
            "inputFiles": [],
            "notes": [],
        },
        "slippage": {"summary": [], "algos": []},
        "risk": {
            "alerts": [],
            "zScores": {},
            "stopLossWatch": [],
            "priceCostDrift": [],
            "exposure": [],
        },
        "dataHealth": empty_data_health(),
    }


def to_record(row: Any) -> dict:
    """Convert a dataclass row to a plain dict (JSON-ready keys)."""
    return asdict(row) if hasattr(row, "__dataclass_fields__") else dict(row)


# --------------------------------------------------------------------------
# Structural validation (shape only; numeric-finiteness is enforced by the
# exporter's validate_payload()).
# --------------------------------------------------------------------------
_REQUIRED_TOP = ("schemaVersion", "runId", "businessDate", "generatedAt",
                 "source", "slippage", "risk", "dataHealth")
_REQUIRED_SOURCE = ("mode", "pipelineEntryPoint", "inputTimestamp",
                    "inputFiles", "notes")
_REQUIRED_HEALTH = ("strictJson", "pipelineStatus", "producerStatus",
                    "lastSuccessfulRunAt", "sectionsPresent",
                    "sectionsMissing", "warnings", "rowCounts")


def validate_structure(payload: dict) -> list[str]:
    """Return a list of structural problems; empty list == OK.

    Enforces the 4.0 contract. Legacy 3.0 payloads will report problems here
    on purpose — callers must route them through `adapt_legacy_v3` first.
    """
    problems: list[str] = []
    for k in _REQUIRED_TOP:
        if k not in payload:
            problems.append(f"missing top-level key: {k}")

    src = payload.get("source", {})
    for k in _REQUIRED_SOURCE:
        if k not in src:
            problems.append(f"missing source.{k}")
    if src.get("mode") not in SOURCE_MODES:
        problems.append(f"source.mode invalid: {src.get('mode')!r}")

    risk = payload.get("risk", {})
    for k in ("alerts", "zScores", "stopLossWatch", "priceCostDrift", "exposure"):
        if k not in risk:
            problems.append(f"missing risk.{k}")

    slip = payload.get("slippage", {})
    for k in ("summary", "algos"):
        if k not in slip:
            problems.append(f"missing slippage.{k}")

    dh = payload.get("dataHealth", {})
    for k in _REQUIRED_HEALTH:
        if k not in dh:
            problems.append(f"missing dataHealth.{k}")
    if dh.get("strictJson") is not True:
        problems.append("dataHealth.strictJson must be true")
    ps = dh.get("pipelineStatus")
    if ps not in PIPELINE_STATUSES:
        problems.append(f"dataHealth.pipelineStatus invalid: {ps!r}")
    prod = dh.get("producerStatus")
    if not isinstance(prod, dict):
        problems.append("dataHealth.producerStatus must be an object")
    else:
        for name, entry in prod.items():
            if not isinstance(entry, dict) or "status" not in entry:
                problems.append(f"producerStatus.{name} malformed")
            elif entry.get("status") not in PRODUCER_STATUSES:
                problems.append(
                    f"producerStatus.{name}.status invalid: {entry.get('status')!r}")

    # Schema-version gate: only known versions are structurally valid here.
    ver = payload.get("schemaVersion")
    if ver not in (SCHEMA_VERSION,):
        problems.append(
            f"schemaVersion must be {SCHEMA_VERSION!r} (got {ver!r}); "
            "route legacy payloads through adapt_legacy_v3")

    return problems


def is_live_mode(payload: dict) -> bool:
    return payload.get("source", {}).get("mode") in LIVE_SOURCE_MODES


def validate_live_health(payload: dict) -> list[str]:
    """Extra checks that apply ONLY to live 4.0 payloads.

    A live payload may not be shown as healthy unless its health block is
    fully populated and internally consistent. Returns problems; empty == OK.
    """
    problems: list[str] = []
    dh = payload.get("dataHealth", {})
    if dh.get("pipelineStatus") == "ok":
        # 'ok' demands evidence: at least one successful producer and a
        # recorded lastSuccessfulRunAt.
        prod = dh.get("producerStatus", {}) or {}
        successes = [p for p, e in prod.items()
                     if isinstance(e, dict) and e.get("status") == "success"]
        if not successes:
            problems.append("pipelineStatus=ok but no successful producers")
        if not dh.get("lastSuccessfulRunAt"):
            problems.append("pipelineStatus=ok but lastSuccessfulRunAt missing")
        # 'unknown' producer status is a legacy-compat marker and may never
        # appear in a healthy live payload.
        unknowns = [p for p, e in prod.items()
                    if isinstance(e, dict) and e.get("status") == "unknown"]
        if unknowns:
            problems.append(
                f"pipelineStatus=ok but producers still unknown: {unknowns}")
    return problems


# --------------------------------------------------------------------------
# Legacy 3.0 compatibility adapter
# --------------------------------------------------------------------------
def is_legacy_v3(payload: dict) -> bool:
    return str(payload.get("schemaVersion", "")).startswith("3.")


def adapt_legacy_v3(payload: dict) -> dict:
    """Convert a legacy 3.0 snapshot into a *structurally* valid 4.0 payload
    WITHOUT ever fabricating health.

    The adapter:
      * identifies the payload as legacy 3.0,
      * NEVER infers pipelineStatus='ok' (it is marked 'stale'),
      * sets every producer's health to 'unknown',
      * attaches a legacy/stale warning,
      * does NOT relabel the data as a healthy live payload.

    The result is intended for read-only display with a clear stale banner.
    It must not be re-published as healthy 4.0 without a real conversion +
    validation step upstream.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")

    out = dict(payload)  # shallow copy; we only touch envelope + health
    out["schemaVersion"] = SCHEMA_VERSION

    src = dict(out.get("source", {}) or {})
    # Legacy 'pipeline-live'/'pipeline-dry-run'/'sample' modes remain valid.
    if src.get("mode") not in SOURCE_MODES:
        src["mode"] = "sample"
    src.setdefault("pipelineEntryPoint", "")
    src.setdefault("inputTimestamp", "")
    src.setdefault("inputFiles", [])
    src.setdefault("notes", [])
    src["notes"] = list(src.get("notes", [])) + [
        "Adapted from legacy schema 3.0 snapshot (read-only, stale)."
    ]
    out["source"] = src

    old_health = dict(out.get("dataHealth", {}) or {})
    producer_status = {
        p: {"status": "unknown", "rowCount": None,
            "capturedAt": None, "error": None}
        for p in PRODUCERS
    }
    warnings = list(old_health.get("warnings", []))
    warnings.insert(
        0,
        "Legacy 3.0 snapshot: producer health is unknown; data is shown as "
        "stale and must not be treated as a fresh healthy run.",
    )
    out["dataHealth"] = {
        "strictJson": old_health.get("strictJson", True) is True,
        "pipelineStatus": "stale",          # never 'ok' without evidence
        "producerStatus": producer_status,  # all unknown
        "lastSuccessfulRunAt": None,
        "sectionsPresent": old_health.get("sectionsPresent", []),
        "sectionsMissing": old_health.get("sectionsMissing", []),
        "warnings": warnings,
        "rowCounts": old_health.get("rowCounts", {}),
    }
    return out
