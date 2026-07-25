"""
IGS Daily Monitor — pipeline → dashboard exporter (Phase 3).

Maps the pipeline's *computed DataFrames* (the SAME objects the email uses,
captured BEFORE any df.to_html()) into the canonical dashboard contract JSON.

SIBLING, NOT CHILD:
  * This module NEVER reads email HTML, email bodies, sent-mail content,
    an inbox, or screenshots.
  * Permitted inputs: live pandas DataFrames from the calc layer; saved
    pipeline artifacts (riskstats_<date>.json, drift/exposure CSV/JSON/parquet);
    built-in sample data for dry-run.

Public API:
  clean_value(v)                     -> JSON-safe scalar (NaN/Inf -> None)
  df_to_records(df, mapping, ...)    -> list[dict] with contract field names
  build_payload_from_bundle(bundle)  -> dict (full contract payload)
  sanitize_payload(payload)          -> payload with all NaN/Inf -> None
  validate_payload(payload)          -> list[str] problems ([] == OK)
  write_payload(payload, path, ...)  -> writes strict JSON (allow_nan=False)

No SQL, no API calls, no email imports.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import os
import uuid
from typing import Any, Iterable, Optional

import dashboard_contract as contract

try:  # pandas is available where the pipeline runs; keep import soft for dry tests
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore


# ==========================================================================
# 1. Scalar cleaning
# ==========================================================================
def clean_value(v: Any) -> Any:
    """Return a JSON-safe scalar. NaN / Inf / pandas-NA / NaT -> None."""
    if v is None:
        return None
    # pandas NA / NaT
    if pd is not None:
        try:
            if v is pd.NA or (not isinstance(v, (list, tuple, dict)) and pd.isna(v)):
                return None
        except (TypeError, ValueError):
            pass
    # floats
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    # numpy scalars -> python
    if pd is not None and hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
        except (ValueError, AttributeError):
            pass
    return v


def parse_percent(v: Any) -> Optional[float]:
    """'3.61%' | 3.61 | '  -0.5 % ' -> 3.61 / -0.5 ; junk/NaN -> None."""
    v = clean_value(v)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("%", "").replace(",", "")
    if not s or s.lower() in ("nan", "none", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_rupees(v: Any) -> Optional[float]:
    """'₹1,23,456.78' | '1,234' | -12.5 -> float ; junk -> None."""
    v = clean_value(v)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("₹", "").replace(",", "").replace("Rs", "").strip()
    if not s or s.lower() in ("nan", "none", "-", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(v: Any) -> Optional[int]:
    f = parse_rupees(v)
    return int(round(f)) if f is not None else None


# ==========================================================================
# 2. DataFrame -> records
# ==========================================================================
def df_to_records(
    df: Any,
    mapping: dict[str, str],
    *,
    converters: Optional[dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """
    Convert a DataFrame to a list of contract dicts.

    mapping    : { source_column : contract_field }
    converters : { contract_field : callable(value) }  (e.g. parse_percent)
    limit      : keep only the first N rows (after any upstream ranking)
    """
    if df is None:
        return []
    converters = converters or {}
    # Accept either a real DataFrame or an already-materialised list of dicts.
    if pd is not None and isinstance(df, pd.DataFrame):
        if df.empty:
            return []
        rows_iter: Iterable[dict] = df.to_dict(orient="records")
    elif isinstance(df, list):
        rows_iter = df
    else:
        return []

    out: list[dict] = []
    for i, src in enumerate(rows_iter):
        if limit is not None and i >= limit:
            break
        rec: dict = {}
        for src_col, field_name in mapping.items():
            raw = src.get(src_col) if isinstance(src, dict) else None
            conv = converters.get(field_name)
            rec[field_name] = clean_value(conv(raw)) if conv else clean_value(raw)
        out.append(rec)
    return out


# ==========================================================================
# 3. Bundle -> payload
#    `bundle` is a plain dict of DataFrames/objects captured by the pipeline
#    calc layer (see dashboard_adapter/collect layer in Phase 4). Every key is
#    optional; missing sections degrade gracefully (tracked in dataHealth).
# ==========================================================================
def build_payload_from_bundle(
    bundle: dict[str, Any],
    *,
    business_date: str,
    mode: str,
    pipeline_entry_point: str = "",
    input_timestamp: str = "",
    input_files: Optional[list[str]] = None,
    notes: Optional[list[str]] = None,
) -> dict[str, Any]:
    now_iso = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    payload = contract.empty_payload(
        business_date,
        mode=mode,
        run_id=str(uuid.uuid4()),
        generated_at=now_iso,
        pipeline_entry_point=pipeline_entry_point,
        input_timestamp=input_timestamp or now_iso,
    )
    payload["source"]["inputFiles"] = list(input_files or [])
    payload["source"]["notes"] = list(notes or [])

    # ---- Slippage summary --------------------------------------------------
    payload["slippage"]["summary"] = df_to_records(
        bundle.get("slippage_summary"),
        {
            "Algo_id": "algoId",
            "Algo_name": "algoName",
            "slippage_model_igs": "slippageModelIgsPct",
            "slippage_close_price": "slippageClosePricePct",
            "slippage_cumulative_igs_daily_close": "cumulativeDailyClosePct",
            "slippage_cumulative_igs_model_close": "cumulativeModelClosePct",
            "todayClosePnl": "todayClosePnl",
            "todayModelPnl": "todayModelPnl",
            "cumulativeDailyClosePnl": "cumulativeDailyClosePnl",
            "cumulativeModelPnl": "cumulativeModelPnl",
        },
        converters={
            "algoId": parse_int,
            "slippageModelIgsPct": parse_percent,
            "slippageClosePricePct": parse_percent,
            "cumulativeDailyClosePct": parse_percent,
            "cumulativeModelClosePct": parse_percent,
            "todayClosePnl": parse_rupees,
            "todayModelPnl": parse_rupees,
            "cumulativeDailyClosePnl": parse_rupees,
            "cumulativeModelPnl": parse_rupees,
        },
    )

    # ---- Slippage per-algo (best/worst/date series) ------------------------
    algos_out: list[dict] = []
    stock_map = {
        "Symbol": "symbol", "symbol": "symbol",
        "Name": "name", "CorpName": "name",
        "Slippage_PnL_₹": "slippagePnlRs",
        "Slippage_pct": "slippagePct",
    }
    stock_conv = {"slippagePnlRs": parse_rupees, "slippagePct": parse_percent}
    for algo in (bundle.get("slippage_algos") or []):
        algo_name = algo.get("algoName", "")
        best = df_to_records(algo.get("best5"), stock_map, converters=stock_conv, limit=5)
        worst = df_to_records(algo.get("worst5"), stock_map, converters=stock_conv, limit=5)
        for r in best:
            r["algoName"], r["rankType"] = algo_name, "best"
        for r in worst:
            r["algoName"], r["rankType"] = algo_name, "worst"
        date_series = df_to_records(
            algo.get("date_dist"),
            {"Date": "date", "Slippage_pct": "slippagePct"},
            converters={"slippagePct": parse_percent},
        )
        for d in date_series:
            d["date"] = "" if d.get("date") is None else str(d["date"])[:10]
        algos_out.append({
            "algoId": parse_int(algo.get("algoId")),
            "algoName": algo_name,
            "headlines": algo.get("headlines", []),
            "bestStocks": best,
            "worstStocks": worst,
            "dateSeries": date_series,
        })
    payload["slippage"]["algos"] = algos_out

    # ---- Alerts ------------------------------------------------------------
    payload["risk"]["alerts"] = df_to_records(
        bundle.get("alerts"),
        {
            "Alert Type": "alertType", "Metric": "metric",
            "Current Value": "currentValue", "Threshold": "threshold",
            "Breach?": "breach", "Action Required": "actionRequired",
            "severity": "severity",
        },
    )
    for a in payload["risk"]["alerts"]:
        b = str(a.get("breach") or "").strip().lower()
        a["breach"] = "Yes" if b in ("yes", "true", "1") else ("No" if b in ("no", "false", "0") else "—")
        if not a.get("severity"):
            a["severity"] = "breach" if a["breach"] == "Yes" else "info"

    # ---- z-scores (derived scalars only) -----------------------------------
    z = bundle.get("zscores") or {}
    payload["risk"]["zScores"] = {
        k: clean_value(z.get(k)) for k in ("composite", "alpha", "combined") if z.get(k) is not None
    }

    # ---- Stop-loss watch ---------------------------------------------------
    payload["risk"]["stopLossWatch"] = df_to_records(
        bundle.get("stop_loss"),
        {
            "symbol": "symbol", "Name": "name",
            "reset_price": "resetPrice", "last_price": "lastPrice",
            "Chg%": "chgPct", "Days Held": "daysHeld",
            "exec_weight%": "execWeightPct", "pct_change%": "pctChangePct",
            "sl_hit": "slHit",
        },
        converters={
            "resetPrice": parse_rupees, "lastPrice": parse_rupees,
            "chgPct": parse_percent, "daysHeld": parse_int,
            "execWeightPct": parse_percent, "pctChangePct": parse_percent,
        },
    )
    for s in payload["risk"]["stopLossWatch"]:
        s["slHit"] = str(s.get("slHit")).strip().lower() in ("true", "yes", "1", "hit")

    # ---- Price / cost drift ------------------------------------------------
    payload["risk"]["priceCostDrift"] = df_to_records(
        bundle.get("price_cost_drift"),
        {
            "algoName": "algoName", "symbol": "symbol", "Name": "name",
            "reset_price": "resetPrice", "Avg Cost": "avgCost",
            "Diff_ResetPrice_AvgPrice": "diffResetPriceAvgPricePct",
            "exec_weight%": "execWeightPct", "Gain/Loss%": "gainLossPct",
        },
        converters={
            "resetPrice": parse_rupees, "avgCost": parse_rupees,
            "diffResetPriceAvgPricePct": parse_percent,
            "execWeightPct": parse_percent, "gainLossPct": parse_percent,
        },
    )
    for d in payload["risk"]["priceCostDrift"]:
        if d.get("diffResetPriceAvgPricePct") is None:
            d["diffResetPriceAvgPricePct"] = 0.0

    # ---- Exposure ----------------------------------------------------------
    payload["risk"]["exposure"] = df_to_records(
        bundle.get("exposure"),
        {
            "algoName": "algoName", "OSID": "osid", "Quantity": "quantity",
            "AvgPrice": "avgPrice", "MarketPrice": "marketPrice", "Isin": "isin",
            "exec_weight%": "execWeightPct", "Gain/Loss%": "gainLossPct",
            "MarketValue": "marketValue", "symbol": "symbol", "coname": "coname",
        },
        converters={
            "osid": parse_int, "quantity": parse_rupees,
            "avgPrice": parse_rupees, "marketPrice": parse_rupees,
            "execWeightPct": parse_percent, "gainLossPct": parse_percent,
            "marketValue": parse_rupees,
        },
    )

    _recompute_health(payload)
    return sanitize_payload(payload)


# ==========================================================================
# 4. dataHealth
# ==========================================================================
def _recompute_health(payload: dict) -> None:
    counts = {
        "slippageSummary": len(payload["slippage"]["summary"]),
        "slippageAlgos": len(payload["slippage"]["algos"]),
        "alerts": len(payload["risk"]["alerts"]),
        "stopLossWatch": len(payload["risk"]["stopLossWatch"]),
        "priceCostDrift": len(payload["risk"]["priceCostDrift"]),
        "exposure": len(payload["risk"]["exposure"]),
        "zScores": len(payload["risk"]["zScores"]),
    }
    present = [s for s in contract.SECTIONS if counts.get(s, 0) > 0]
    missing = [s for s in contract.SECTIONS if counts.get(s, 0) == 0]
    warnings = list(payload["dataHealth"].get("warnings", []))
    for s in missing:
        warnings.append(f"Section '{s}' is empty.")
    payload["dataHealth"].update({
        "strictJson": True,
        "sectionsPresent": present,
        "sectionsMissing": missing,
        "warnings": warnings,
        "rowCounts": counts,
    })


# ==========================================================================
# 5. Sanitize / validate / write
# ==========================================================================
def sanitize_payload(payload: Any) -> Any:
    """Recursively replace NaN/Inf/NA with None throughout the payload."""
    if isinstance(payload, dict):
        return {k: sanitize_payload(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [sanitize_payload(v) for v in payload]
    return clean_value(payload)


def _find_bad_floats(obj: Any, path: str = "$") -> list[str]:
    bad: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad += _find_bad_floats(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            bad += _find_bad_floats(v, f"{path}[{i}]")
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        bad.append(path)
    return bad


def validate_payload(payload: dict) -> list[str]:
    """Structural + numeric-finiteness validation. [] == OK."""
    problems = contract.validate_structure(payload)
    problems += [f"non-finite float at {p}" for p in _find_bad_floats(payload)]
    # try a strict serialization as the ultimate guard
    try:
        json.dumps(payload, allow_nan=False)
    except (ValueError, TypeError) as e:
        problems.append(f"strict json.dumps failed: {e}")
    return problems


def write_payload(
    payload: dict,
    path: str,
    *,
    also_dated: bool = True,
    validate: bool = True,
) -> list[str]:
    """
    Write the payload as STRICT JSON (allow_nan=False). Returns paths written.
    Raises ValueError if validate=True and validation fails.
    """
    payload = sanitize_payload(payload)
    if validate:
        problems = validate_payload(payload)
        if problems:
            raise ValueError("payload validation failed:\n  - " + "\n  - ".join(problems))

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    written: list[str] = []
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, allow_nan=False)
    written.append(path)

    if also_dated:
        bd = payload.get("businessDate") or _dt.date.today().isoformat()
        dated = os.path.join(os.path.dirname(os.path.abspath(path)),
                             f"dashboard_payload_{bd}.json")
        with open(dated, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, allow_nan=False)
        written.append(dated)
    return written
