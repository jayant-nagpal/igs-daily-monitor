#!/usr/bin/env python3
"""
IGS Daily Monitor — Dashboard Data Adapter
===========================================

Transforms *already-produced* IGS pipeline output into a single clean
``latest.json`` that the React dashboard consumes.

This adapter is intentionally decoupled from the production pipeline:

  * It NEVER sends email.
  * It NEVER connects to SQL / ExecAPI / RiskAPI / SignalStore or any internal API.
  * It NEVER imports or runs the existing production scripts.
  * It ONLY reads files that the pipeline has already written (JSON / CSV / HTML)
    or a manually supplied JSON file, normalises them, and writes dashboard JSON.

Input modes
-----------
Mode 1 (preferred)  : structured JSON or CSV files exported from the pipeline
                      output folder.               --input-dir ./pipeline_output
Mode 2 (fallback)   : saved HTML files containing the same pandas tables used in
                      the email body (parsed with pandas.read_html).
                      Auto-detected inside --input-dir.
Mode 3 (manual)     : a single JSON file already matching the dashboard schema.
                                                    --input ./latest_raw.json
Mode "sample"       : if no real input is supplied, the built-in screenshot
                      sample data is emitted so the dashboard works immediately.

Usage
-----
    python dashboard_adapter/build_dashboard_payload.py \\
        --input-dir ./pipeline_output \\
        --output ./igs-daily-monitor/public/data/latest.json

    python dashboard_adapter/build_dashboard_payload.py \\
        --input ./pipeline_output/latest_raw.json \\
        --output ./igs-daily-monitor/public/data/latest.json

    # no real files yet -> emit sample payload
    python dashboard_adapter/build_dashboard_payload.py \\
        --output ./igs-daily-monitor/public/data/latest.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import io
import json
import math
import os
import re
import sys
from typing import Any

# pandas / bs4 are only required for CSV and HTML modes. Import lazily so that
# JSON / sample mode works on a bare standard-library environment.
try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas is listed in requirements.txt
    pd = None


ALGO_ID_MAP = {24: "ALGO-A", 85: "ALGO-B", 187: "ALGO-B2"}
REQUIRED_SECTIONS = ["slippage", "risk"]
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# 1. Arguments
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build IGS Daily Monitor dashboard payload (latest.json).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # PRODUCTION path: --mode selects the sibling pipeline exporter.
    #   pipeline | dry-run | sample   (and the deprecated legacy-email-html-demo)
    p.add_argument("--mode", type=str, default=None,
                   choices=["pipeline", "dry-run", "sample", "legacy-email-html-demo"],
                   help="pipeline = live sibling export (DB); dry-run = sample DataFrames; "
                        "sample = built-in demo data; legacy-email-html-demo = DEPRECATED.")
    p.add_argument("--confirm-safe-run", action="store_true",
                   help="Required for --mode pipeline (live DB/API access).")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--input-dir", type=str, default=None,
                     help="[legacy-email-html-demo only] Folder of pipeline output files.")
    src.add_argument("--input", type=str, default=None,
                     help="[legacy-email-html-demo only] Single schema-shaped JSON file.")
    p.add_argument("--output", type=str, required=True,
                   help="Destination latest.json path.")
    p.add_argument("--business-date", type=str, default=None,
                   help="Override business date (YYYY-MM-DD).")
    p.add_argument("--no-dated-copy", action="store_true",
                   help="Do not also write dashboard_payload_YYYY-MM-DD.json.")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# 2. Numeric normalisers
# ---------------------------------------------------------------------------
def parse_percent(value: Any) -> float | None:
    """'0.1207%' -> 0.1207 ; '-0.00%' -> -0.0 ; -16.45 -> -16.45 ; None -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if isinstance(value, float) and math.isnan(value) else float(value)
    s = str(value).strip()
    if s in ("", "-", "—", "nan", "None"):
        return None
    neg = s.startswith("-")
    s = s.replace("%", "").replace(",", "").strip()
    try:
        num = float(s)
    except ValueError:
        return None
    # preserve an explicit "-0.00%" as negative zero (spec requirement)
    if num == 0.0 and neg:
        return -0.0
    return num


def parse_rupees(value: Any) -> float | None:
    """'₹1,182.60' / '-1,182.60' / 171315.33 -> float ; blanks -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if isinstance(value, float) and math.isnan(value) else float(value)
    s = str(value).strip()
    if s in ("", "-", "—", "nan", "None"):
        return None
    s = s.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
    m = re.match(r"^-?\d*\.?\d+$", s)
    if not m:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    f = parse_rupees(value)
    return int(round(f)) if f is not None else None


def normalize_columns(cols: list[str]) -> list[str]:
    """Lowercase, strip, collapse whitespace/underscores for fuzzy matching."""
    out = []
    for c in cols:
        c2 = str(c).strip().lower()
        c2 = c2.replace("&", "and").replace("?", "")
        c2 = re.sub(r"[\s_/%().₹-]+", "_", c2).strip("_")
        out.append(c2)
    return out


# ---------------------------------------------------------------------------
# 3. Empty payload skeleton
# ---------------------------------------------------------------------------
def empty_payload(business_date: str, mode: str) -> dict:
    return {
        "businessDate": business_date,
        "generatedAt": dt.datetime.now(IST).isoformat(timespec="seconds"),
        "source": {"mode": mode, "inputFiles": [], "notes": []},
        "slippage": {"summary": [], "algos": []},
        "risk": {
            "alerts": [],
            "zScores": {},
            "stopLossWatch": [],
            "priceCostDrift": [],
            "exposure": [],
        },
        "dataHealth": {
            "sectionsPresent": [],
            "sectionsMissing": [],
            "warnings": [],
            "rowCounts": {},
        },
    }


# ---------------------------------------------------------------------------
# 4. Input discovery + loaders
# ---------------------------------------------------------------------------
def load_input_files(input_dir: str) -> dict[str, list[str]]:
    files = {"json": [], "csv": [], "html": []}
    if not input_dir or not os.path.isdir(input_dir):
        return files
    for path in sorted(glob.glob(os.path.join(input_dir, "**", "*"), recursive=True)):
        low = path.lower()
        if low.endswith(".json"):
            files["json"].append(path)
        elif low.endswith(".csv"):
            files["csv"].append(path)
        elif low.endswith((".html", ".htm")):
            files["html"].append(path)
    return files


def parse_json_input(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 5. Table classification (shared by CSV and HTML modes)
# ---------------------------------------------------------------------------
def classify_table(norm_cols: list[str]) -> str | None:
    """Infer table type from normalised column names. Mirrors the real
    email tables produced by slippage_calc.py and stoploss_check.py."""
    cset = set(norm_cols)

    def has(*names): return all(n in cset for n in names)
    def any_of(*names): return any(n in cset for n in names)

    # slippage summary: Algo_id, Algo_name, slippage_model_igs ...
    if has("algo_id", "algo_name") and any_of(
        "slippage_model_igs", "slippage_close_price", "slippage_cumulative_igs_daily_close"
    ):
        return "slippage_summary"
    # slippage headline: Metric, Slippage, P&L
    if has("metric", "slippage") and any_of("p_and_l", "pnl", "p_l"):
        return "slippage_headline"
    # best/worst stocks: Symbol, Name, Slippage_PnL_₹
    if has("symbol", "name") and any_of("slippage_pnl", "slippage_pnl_rs"):
        return "slippage_stocks"
    # alert table: Alert Type, Metric, Current Value, Threshold
    if has("alert_type", "metric", "current_value", "threshold"):
        return "alerts"
    # stop-loss watch: symbol, reset_price, last_price, pct_change%, sl_hit
    if has("symbol", "reset_price", "last_price") and any_of("pct_change", "sl_hit"):
        return "stop_loss_watch"
    # exposure: algoName, OSID, Quantity, AvgPrice, MarketPrice, exec_weight%
    if any_of("osid") and has("quantity") and any_of("avgprice", "avg_price") \
            and any_of("marketprice", "market_price"):
        return "exposure"
    # price-cost drift: reset_price, Avg Cost, Diff_ResetPrice_AvgPrice
    if any_of("diff_resetprice_avgprice", "diff_resetprice_avgprice_pct",
              "diff_reset_price_avg_price") or (
            has("reset_price", "avg_cost") and any_of("diff", "diff_resetprice_avgprice")):
        return "price_cost_drift"
    return None


def _col(df, norm_cols, *candidates):
    """Return the *original* column name whose normalised form matches any candidate."""
    for cand in candidates:
        if cand in norm_cols:
            return df.columns[norm_cols.index(cand)]
    return None


def _algo_from_context(context: str) -> str:
    c = (context or "").upper()
    if "ALGO-B2" in c or "ALGO-B2" in c or "ALGO-BII" in c or "187" in c:
        return "ALGO-B2"
    if "ALGO-B" in c or "85" in c:
        return "ALGO-B"
    if "ALGO-A" in c or "24" in c:
        return "ALGO-A"
    return ""


# ---------------------------------------------------------------------------
# 6. Row extractors -> schema fragments
# ---------------------------------------------------------------------------
def _extract_slippage_summary(df, norm) -> list[dict]:
    rows = []
    for _, r in df.iterrows():
        aid = parse_int(r.get(_col(df, norm, "algo_id")))
        aname = str(r.get(_col(df, norm, "algo_name")) or ALGO_ID_MAP.get(aid, "")).strip()
        rows.append({
            "algoId": aid,
            "algoName": aname,
            "slippageModelIgsPct": parse_percent(r.get(_col(df, norm, "slippage_model_igs"))),
            "slippageClosePricePct": parse_percent(r.get(_col(df, norm, "slippage_close_price"))),
            "cumulativeDailyClosePct": parse_percent(r.get(_col(df, norm, "slippage_cumulative_igs_daily_close"))),
            "cumulativeModelClosePct": parse_percent(r.get(_col(df, norm, "slippage_cumulative_igs_model_close"))),
            "todayClosePnl": None,
            "todayModelPnl": None,
            "cumulativeDailyClosePnl": None,
            "cumulativeModelPnl": None,
        })
    return rows


def _extract_stocks(df, norm, context) -> list[dict]:
    sym = _col(df, norm, "symbol")
    name = _col(df, norm, "name")
    pnl = _col(df, norm, "slippage_pnl", "slippage_pnl_rs")
    pct = _col(df, norm, "slippage_pct", "slippage")
    algo = _algo_from_context(context)
    out = []
    for _, r in df.iterrows():
        out.append({
            "algoName": algo,
            "rankType": "best" if "best" in (context or "").lower() else "worst",
            "symbol": str(r.get(sym) or "").strip(),
            "name": str(r.get(name) or "").strip(),
            "slippagePnlRs": parse_rupees(r.get(pnl)),
            "slippagePct": parse_percent(r.get(pct)),
        })
    return out


def _extract_alerts(df, norm) -> list[dict]:
    at = _col(df, norm, "alert_type")
    me = _col(df, norm, "metric")
    cv = _col(df, norm, "current_value")
    th = _col(df, norm, "threshold")
    br = _col(df, norm, "breach")
    ar = _col(df, norm, "action_required")
    out = []
    for _, r in df.iterrows():
        breach = str(r.get(br) or "—").strip()
        action = str(r.get(ar) or "").strip()
        sev = _alert_severity(breach, action)
        out.append({
            "alertType": str(r.get(at) or "").strip(),
            "metric": str(r.get(me) or "").strip(),
            "currentValue": str(r.get(cv) or "").strip(),
            "threshold": str(r.get(th) or "").strip(),
            "breach": breach if breach in ("Yes", "No", "—") else "—",
            "actionRequired": action,
            "severity": sev,
        })
    return out


def _alert_severity(breach: str, action: str) -> str:
    b = (breach or "").strip().lower()
    a = (action or "").strip().lower()
    if b == "yes":
        return "breach"
    if "informational" in a:
        return "info"
    if b == "no":
        return "ok"
    return "info"


def _extract_stop_loss(df, norm) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        pct_change = parse_percent(r.get(_col(df, norm, "pct_change", "pct_change_pct")))
        sl = r.get(_col(df, norm, "sl_hit"))
        out.append({
            "symbol": str(r.get(_col(df, norm, "symbol")) or "").strip(),
            "name": str(r.get(_col(df, norm, "name")) or "").strip(),
            "resetPrice": parse_rupees(r.get(_col(df, norm, "reset_price"))),
            "lastPrice": parse_rupees(r.get(_col(df, norm, "last_price"))),
            "chgPct": parse_percent(r.get(_col(df, norm, "chg", "chg_pct"))),
            "daysHeld": parse_int(r.get(_col(df, norm, "days_held"))),
            "execWeightPct": parse_percent(r.get(_col(df, norm, "exec_weight"))),
            "pctChangePct": pct_change,
            "slHit": str(sl).strip().lower() in ("true", "1", "yes"),
        })
    return out


def _extract_price_cost_drift(df, norm, context) -> list[dict]:
    algo = _algo_from_context(context) or "ALGO-A"
    algo = {"ALGO-B2": "ALGO-B2"}.get(algo, algo)
    out = []
    for _, r in df.iterrows():
        out.append({
            "algoName": algo,
            "symbol": str(r.get(_col(df, norm, "symbol")) or "").strip(),
            "name": str(r.get(_col(df, norm, "name")) or "").strip(),
            "resetPrice": parse_rupees(r.get(_col(df, norm, "reset_price"))),
            "avgCost": parse_rupees(r.get(_col(df, norm, "avg_cost"))),
            "diffResetPriceAvgPricePct": parse_percent(
                r.get(_col(df, norm, "diff_resetprice_avgprice", "diff_reset_price_avg_price", "diff"))),
            "execWeightPct": parse_percent(r.get(_col(df, norm, "exec_weight"))),
            "gainLossPct": parse_percent(r.get(_col(df, norm, "gain_loss", "gain_loss_pct"))),
        })
    return out


def _extract_exposure(df, norm) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        out.append({
            "algoName": str(r.get(_col(df, norm, "algoname", "algo_name")) or "").strip(),
            "osid": parse_int(r.get(_col(df, norm, "osid"))),
            "quantity": parse_int(r.get(_col(df, norm, "quantity"))),
            "avgPrice": parse_rupees(r.get(_col(df, norm, "avgprice", "avg_price"))),
            "marketPrice": parse_rupees(r.get(_col(df, norm, "marketprice", "market_price"))),
            "isin": str(r.get(_col(df, norm, "isin")) or "").strip(),
            "execWeightPct": parse_percent(r.get(_col(df, norm, "exec_weight"))),
            "gainLossPct": parse_percent(r.get(_col(df, norm, "gain_loss", "gain_loss_pct"))),
            "marketValue": parse_rupees(r.get(_col(df, norm, "marketvalue", "market_value"))),
            "symbol": str(r.get(_col(df, norm, "symbol")) or "").strip(),
            "coname": str(r.get(_col(df, norm, "coname", "name")) or "").strip(),
        })
    return out


# ---------------------------------------------------------------------------
# 7. CSV mode
# ---------------------------------------------------------------------------
def parse_csv_inputs(csv_files: list[str], payload: dict) -> None:
    if pd is None:
        payload["dataHealth"]["warnings"].append("pandas not available; CSV mode skipped.")
        return
    for path in csv_files:
        try:
            df = pd.read_csv(path)
        except Exception as e:  # noqa: BLE001
            payload["dataHealth"]["warnings"].append(f"Failed to read CSV {os.path.basename(path)}: {e}")
            continue
        _route_table(df, payload, context=os.path.basename(path))


# ---------------------------------------------------------------------------
# 8. HTML mode (pandas.read_html)
# ---------------------------------------------------------------------------
def parse_html_tables(html_files: list[str], payload: dict) -> None:
    if pd is None:
        payload["dataHealth"]["warnings"].append("pandas not available; HTML mode skipped.")
        return
    for path in html_files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
            # capture nearby <h3>/<h4> headings so best/worst + algo can be inferred.
            # wrap in StringIO: newer pandas rejects a raw HTML string literal.
            tables = pd.read_html(io.StringIO(raw))
        except Exception as e:  # noqa: BLE001
            payload["dataHealth"]["warnings"].append(f"read_html failed for {os.path.basename(path)}: {e}")
            continue
        # For each <table> occurrence, gather ALL heading text that precedes it
        # (algo <h3> + best/worst <h4>) so context detection is robust to the
        # interleaving of headings and tables in the email body.
        contexts = _table_contexts(raw, len(tables), os.path.basename(path))
        for i, df in enumerate(tables):
            _route_table(df, payload, context=contexts[i], source_file=os.path.basename(path))


def _table_contexts(raw: str, n_tables: int, fallback: str) -> list[str]:
    """Return, for each <table> in order, the concatenated text of the headings
    that appear since the previous table (captures both the algo <h3> and the
    best/worst <h4>)."""
    tokens = re.findall(r"<h[1-4][^>]*>.*?</h[1-4]>|<table.*?</table>",
                        raw, flags=re.I | re.S)
    contexts: list[str] = []
    pending: list[str] = []
    for tok in tokens:
        if tok.lower().startswith("<table"):
            contexts.append(" | ".join(pending) if pending else fallback)
            pending = []
        else:
            pending.append(re.sub("<[^>]+>", "", tok).strip())
    while len(contexts) < n_tables:
        contexts.append(fallback)
    return contexts


def _route_table(df, payload: dict, context: str = "", source_file: str = "") -> None:
    if pd is None or df is None or len(df) == 0:
        return
    # flatten any MultiIndex columns
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = [" ".join(str(x) for x in tup).strip() for tup in df.columns]
    norm = normalize_columns(list(df.columns))
    kind = classify_table(norm)
    if kind is None:
        payload["dataHealth"]["warnings"].append(
            f"Unclassified table (context='{context}', shape={df.shape}, cols={list(df.columns)})"
        )
        return
    if kind == "slippage_summary":
        payload["slippage"]["summary"].extend(_extract_slippage_summary(df, norm))
    elif kind == "slippage_stocks":
        stocks = _extract_stocks(df, norm, context)
        _merge_stocks_into_algos(payload, stocks)
    elif kind == "alerts":
        payload["risk"]["alerts"].extend(_extract_alerts(df, norm))
        _fill_zscores_from_alerts(payload)
    elif kind == "stop_loss_watch":
        payload["risk"]["stopLossWatch"].extend(_extract_stop_loss(df, norm))
    elif kind == "price_cost_drift":
        payload["risk"]["priceCostDrift"].extend(_extract_price_cost_drift(df, norm, context))
    elif kind == "exposure":
        payload["risk"]["exposure"].extend(_extract_exposure(df, norm))
    elif kind == "slippage_headline":
        pass  # headline metrics are re-derivable from summary; not required for v1


def _merge_stocks_into_algos(payload: dict, stocks: list[dict]) -> None:
    if not stocks:
        return
    algo_name = stocks[0]["algoName"] or "ALGO-A"
    rank = stocks[0]["rankType"]
    algos = payload["slippage"]["algos"]
    algo = next((a for a in algos if a["algoName"] == algo_name), None)
    if algo is None:
        aid = next((k for k, v in ALGO_ID_MAP.items() if v == algo_name), None)
        algo = {"algoId": aid, "algoName": algo_name, "headlines": [],
                "bestStocks": [], "worstStocks": []}
        algos.append(algo)
    algo["bestStocks" if rank == "best" else "worstStocks"].extend(stocks)


def _fill_zscores_from_alerts(payload: dict) -> None:
    for a in payload["risk"]["alerts"]:
        t = a["alertType"].lower()
        val = parse_percent(a["currentValue"])
        if val is None:
            continue
        if "combined" in t:
            payload["risk"]["zScores"]["combined"] = val
        elif "alpha" in t:
            payload["risk"]["zScores"]["alpha"] = val
        elif "composite z-score" in t:
            payload["risk"]["zScores"]["composite"] = val


# ---------------------------------------------------------------------------
# 9. Payload assembly / validation / write
# ---------------------------------------------------------------------------
def build_payload(args: argparse.Namespace) -> dict:
    """Dispatch to the correct input mode and return a normalised payload."""
    business_date = args.business_date or SAMPLE_BUSINESS_DATE

    # Mode 3: manual single JSON
    if args.input:
        raw = parse_json_input(args.input)
        payload = _coerce_manual_json(raw, business_date)
        payload["source"]["mode"] = "json"
        payload["source"]["inputFiles"] = [os.path.basename(args.input)]
        return payload

    # Mode 1 / 2: input directory
    if args.input_dir:
        files = load_input_files(args.input_dir)
        # Prefer a single schema-shaped JSON if present
        for jf in files["json"]:
            try:
                raw = parse_json_input(jf)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(raw, dict) and "slippage" in raw and "risk" in raw:
                payload = _coerce_manual_json(raw, business_date)
                payload["source"]["mode"] = "json"
                payload["source"]["inputFiles"] = [os.path.basename(jf)]
                return payload

        has_csv, has_html = bool(files["csv"]), bool(files["html"])
        if has_csv or has_html:
            mode = "csv" if has_csv and not has_html else ("html" if has_html and not has_csv else "csv")
            payload = empty_payload(business_date, mode)
            all_files = files["csv"] + files["html"]
            payload["source"]["inputFiles"] = [os.path.basename(p) for p in all_files]
            if has_csv:
                parse_csv_inputs(files["csv"], payload)
            if has_html:
                parse_html_tables(files["html"], payload)
                if has_csv:
                    payload["source"]["mode"] = "csv"
            return payload

        # nothing usable found
        payload = _sample_payload(business_date)
        payload["source"]["notes"].append(
            f"No JSON/CSV/HTML files found in {args.input_dir}; emitted sample payload.")
        return payload

    # Mode "sample": no input supplied
    return _sample_payload(business_date)


def _coerce_manual_json(raw: dict, business_date: str) -> dict:
    """Validate + numerically normalise a schema-shaped JSON payload."""
    payload = empty_payload(raw.get("businessDate", business_date), "json")
    payload["businessDate"] = raw.get("businessDate", business_date)
    payload["generatedAt"] = raw.get("generatedAt", payload["generatedAt"])
    payload["source"].update({k: raw.get("source", {}).get(k, v)
                              for k, v in payload["source"].items()})

    sl = raw.get("slippage", {})
    payload["slippage"]["summary"] = [_norm_summary(r) for r in sl.get("summary", [])]
    payload["slippage"]["algos"] = [_norm_algo(a) for a in sl.get("algos", [])]

    rk = raw.get("risk", {})
    payload["risk"]["alerts"] = [_norm_alert(a) for a in rk.get("alerts", [])]
    payload["risk"]["zScores"] = rk.get("zScores", {}) or {}
    payload["risk"]["stopLossWatch"] = [_norm_slw(r) for r in rk.get("stopLossWatch", [])]
    payload["risk"]["priceCostDrift"] = [_norm_drift(r) for r in rk.get("priceCostDrift", [])]
    payload["risk"]["exposure"] = [_norm_exposure(r) for r in rk.get("exposure", [])]
    if not payload["risk"]["zScores"]:
        _fill_zscores_from_alerts(payload)
    return payload


def _num(v, kind="rs"):
    return parse_percent(v) if kind == "pct" else parse_rupees(v)


def _norm_summary(r):
    return {
        "algoId": parse_int(r.get("algoId")),
        "algoName": r.get("algoName"),
        "slippageModelIgsPct": _num(r.get("slippageModelIgsPct"), "pct"),
        "slippageClosePricePct": _num(r.get("slippageClosePricePct"), "pct"),
        "cumulativeDailyClosePct": _num(r.get("cumulativeDailyClosePct"), "pct"),
        "cumulativeModelClosePct": _num(r.get("cumulativeModelClosePct"), "pct"),
        "todayClosePnl": _num(r.get("todayClosePnl")),
        "todayModelPnl": _num(r.get("todayModelPnl")),
        "cumulativeDailyClosePnl": _num(r.get("cumulativeDailyClosePnl")),
        "cumulativeModelPnl": _num(r.get("cumulativeModelPnl")),
    }


def _norm_algo(a):
    return {
        "algoId": parse_int(a.get("algoId")),
        "algoName": a.get("algoName"),
        "headlines": [
            {"metric": h.get("metric"), "slippagePct": _num(h.get("slippagePct"), "pct"),
             "pnlRs": _num(h.get("pnlRs"))}
            for h in a.get("headlines", [])
        ],
        "bestStocks": [_norm_stock(s, "best") for s in a.get("bestStocks", [])],
        "worstStocks": [_norm_stock(s, "worst") for s in a.get("worstStocks", [])],
        **({"dateSeries": a["dateSeries"]} if a.get("dateSeries") else {}),
    }


def _norm_stock(s, rank):
    return {
        "algoName": s.get("algoName"),
        "rankType": s.get("rankType", rank),
        "symbol": s.get("symbol"),
        "name": s.get("name"),
        "slippagePnlRs": _num(s.get("slippagePnlRs")),
        "slippagePct": _num(s.get("slippagePct"), "pct"),
    }


def _norm_alert(a):
    breach = str(a.get("breach", "—"))
    return {
        "alertType": a.get("alertType"),
        "metric": a.get("metric"),
        "currentValue": str(a.get("currentValue", "")),
        "threshold": str(a.get("threshold", "")),
        "breach": breach if breach in ("Yes", "No", "—") else "—",
        "actionRequired": a.get("actionRequired", ""),
        "severity": a.get("severity") or _alert_severity(breach, a.get("actionRequired", "")),
    }


def _norm_slw(r):
    return {
        "symbol": r.get("symbol"), "name": r.get("name"),
        "resetPrice": _num(r.get("resetPrice")), "lastPrice": _num(r.get("lastPrice")),
        "chgPct": _num(r.get("chgPct"), "pct"), "daysHeld": parse_int(r.get("daysHeld")),
        "execWeightPct": _num(r.get("execWeightPct"), "pct"),
        "pctChangePct": _num(r.get("pctChangePct"), "pct"),
        "slHit": bool(r.get("slHit")),
    }


def _norm_drift(r):
    return {
        "algoName": r.get("algoName"), "symbol": r.get("symbol"), "name": r.get("name"),
        "resetPrice": _num(r.get("resetPrice")), "avgCost": _num(r.get("avgCost")),
        "diffResetPriceAvgPricePct": _num(r.get("diffResetPriceAvgPricePct"), "pct"),
        "execWeightPct": _num(r.get("execWeightPct"), "pct"),
        "gainLossPct": _num(r.get("gainLossPct"), "pct"),
    }


def _norm_exposure(r):
    return {
        "algoName": r.get("algoName"), "osid": parse_int(r.get("osid")),
        "quantity": parse_int(r.get("quantity")), "avgPrice": _num(r.get("avgPrice")),
        "marketPrice": _num(r.get("marketPrice")), "isin": r.get("isin"),
        "execWeightPct": _num(r.get("execWeightPct"), "pct"),
        "gainLossPct": _num(r.get("gainLossPct"), "pct"),
        "marketValue": _num(r.get("marketValue")),
        "symbol": r.get("symbol"), "coname": r.get("coname"),
    }


def validate_payload(payload: dict) -> dict:
    """Populate dataHealth from what actually landed in the payload."""
    present, missing, counts = [], [], {}

    counts["slippageSummary"] = len(payload["slippage"]["summary"])
    counts["slippageAlgos"] = len(payload["slippage"]["algos"])
    counts["alerts"] = len(payload["risk"]["alerts"])
    counts["stopLossWatch"] = len(payload["risk"]["stopLossWatch"])
    counts["priceCostDrift"] = len(payload["risk"]["priceCostDrift"])
    counts["exposure"] = len(payload["risk"]["exposure"])
    counts["zScores"] = len(payload["risk"]["zScores"])

    section_map = {
        "slippage.summary": counts["slippageSummary"],
        "slippage.algos": counts["slippageAlgos"],
        "risk.alerts": counts["alerts"],
        "risk.zScores": counts["zScores"],
        "risk.stopLossWatch": counts["stopLossWatch"],
        "risk.priceCostDrift": counts["priceCostDrift"],
        "risk.exposure": counts["exposure"],
    }
    for name, n in section_map.items():
        (present if n > 0 else missing).append(name)

    payload["dataHealth"]["sectionsPresent"] = present
    payload["dataHealth"]["sectionsMissing"] = missing
    payload["dataHealth"]["rowCounts"] = counts

    for req in REQUIRED_SECTIONS:
        if req not in payload or not payload[req]:
            payload["dataHealth"]["warnings"].append(f"Required section missing: {req}")
    return payload


def _sanitize(obj: Any) -> Any:
    """Recursively convert non-finite floats (NaN/Inf) to None so the output is
    STRICT JSON. Browsers' JSON.parse rejects bare NaN/Infinity; if any slips
    through the dashboard silently falls back to sample data."""
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def write_payload(payload: dict, output: str, write_dated: bool = True) -> list[str]:
    os.makedirs(os.path.dirname(os.path.abspath(output)) or ".", exist_ok=True)
    payload = _sanitize(payload)
    written = []
    # allow_nan=False guarantees we never emit invalid JSON (NaN/Infinity).
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
    written.append(output)
    if write_dated:
        dated = os.path.join(
            os.path.dirname(os.path.abspath(output)),
            f"dashboard_payload_{payload['businessDate']}.json",
        )
        with open(dated, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, allow_nan=False)
        written.append(dated)
    return written


# ---------------------------------------------------------------------------
# 10. Built-in sample data (from the report screenshots)
# ---------------------------------------------------------------------------
SAMPLE_BUSINESS_DATE = "2026-07-06"

from sample_data import build_sample_payload  # noqa: E402  (local module)


def _sample_payload(business_date: str) -> dict:
    payload = build_sample_payload(business_date)
    payload["generatedAt"] = dt.datetime.now(IST).isoformat(timespec="seconds")
    return payload


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    # make local sample_data importable regardless of CWD
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    args = parse_args(argv)

    # -------- PRODUCTION routing via --mode (sibling pipeline exporter) ------
    if args.mode in ("pipeline", "dry-run", "sample"):
        import export_dashboard as ed  # local module
        import pipeline_exporter as _px
        business_date = args.business_date or SAMPLE_BUSINESS_DATE
        ex_mode = {"pipeline": "pipeline-live", "dry-run": "pipeline-dry-run",
                   "sample": "sample"}[args.mode]
        bundle = ed.collect_daily_report_data(
            mode=ex_mode, business_date=business_date,
            confirm_safe_run=args.confirm_safe_run)
        ed.send_existing_email(bundle)  # explicit no-op; email stays untouched
        out_dir = os.path.dirname(os.path.abspath(args.output)) or "."
        payload = _px.build_payload_from_bundle(
            bundle, business_date=business_date, mode=ex_mode,
            pipeline_entry_point=f"build_dashboard_payload --mode {args.mode}",
            input_files=["<in-memory pipeline DataFrames>"] if ex_mode.startswith("pipeline")
            else ["<built-in sample>"], notes=bundle.get("_notes", []))
        written = _px.write_payload(payload, args.output,
                                    also_dated=not args.no_dated_copy, validate=True)
        _print_summary(payload, written)
        return 0

    if args.mode == "legacy-email-html-demo":
        print("[DEPRECATED] --mode legacy-email-html-demo: Deprecated demo mode only. "
              "Production dashboard must use pipeline mode, not email HTML.")
        # fall through to legacy input-dir/input handling below

    payload = build_payload(args)
    payload = validate_payload(payload)
    written = write_payload(payload, args.output, write_dated=not args.no_dated_copy)

    _print_summary(payload, written)
    return 0


def _print_summary(payload: dict, written: list[str]) -> None:
    c = payload["dataHealth"]["rowCounts"]
    print("IGS Daily Monitor — dashboard payload built")
    print(f"  mode           : {payload['source']['mode']}")
    print(f"  business date  : {payload['businessDate']}")
    print(f"  input files    : {payload['source']['inputFiles'] or '(none / sample)'}")
    print(f"  slippage rows  : summary={c['slippageSummary']} algos={c['slippageAlgos']}")
    print(f"  risk rows      : alerts={c['alerts']} stopLoss={c['stopLossWatch']} "
          f"drift={c['priceCostDrift']} exposure={c['exposure']} zScores={c['zScores']}")
    print(f"  sections missing: {payload['dataHealth']['sectionsMissing'] or 'none'}")
    if payload["dataHealth"]["warnings"]:
        print(f"  warnings       : {len(payload['dataHealth']['warnings'])}")
        for w in payload["dataHealth"]["warnings"]:
            print(f"     - {w}")
    print("  written        :")
    for p in written:
        print(f"     - {p}")


if __name__ == "__main__":
    raise SystemExit(main())
