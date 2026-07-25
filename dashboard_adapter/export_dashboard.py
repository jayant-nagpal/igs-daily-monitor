"""
IGS Daily Monitor — dashboard export entry point (Phase 4, wrapper pattern).

This is the SIBLING of email generation. It is a *separate, additive* entry
point: it does NOT modify main.py, send_alerts_mail.py, slippage_calc.py, or
any other existing email/pipeline script. The existing daily email keeps
running exactly as before, untouched.

Three functions define the sibling architecture:

  collect_daily_report_data(...)  -> ReportBundle (dict of computed DataFrames)
                                     NO email side effects, NO HTML.
  send_existing_email(bundle)     -> pass-through marker. The REAL email is
                                     produced by the existing, unmodified
                                     pipeline scripts; this wrapper never
                                     re-implements or alters them.
  export_dashboard_payload(bundle)-> maps DataFrames -> contract JSON via
                                     pipeline_exporter, writes latest.json.

SAFETY
  * Never reads email HTML / body / screenshots / inbox.
  * Live mode requires an explicit safe-run confirmation and pipeline
    credentials; otherwise it refuses and falls back to dry-run/sample.
  * Default behaviour = do nothing to email. Export happens ONLY when
    explicitly enabled via CLI flag or IGS_DASHBOARD_EXPORT=1.

MODES
  artifact-live  DEFAULT production path — handled by finalize_dashboard_run.py
                 (reads captured artifacts, fails closed). NOT recomputed here.
  direct-live    Library entry point: adopt an in-memory ReportBundle handed
                 from the email calc layer. NEVER recomputes. Requires
                 confirm_safe_run=True and a supplied report_bundle.
  pipeline-dry-run / sample  Offline sample DataFrames (no DB/API/email).

CLI
  python export_dashboard.py --dashboard-export \
        --dashboard-output-dir dashboard_data \
        [--dry-run] [--no-email] [--business-date YYYY-MM-DD] \
        [--mode pipeline-dry-run|sample] \
        [--confirm-safe-run|--confirm-live]
  (artifact-live and direct-live are refused from the CLI — see MODES.)

ENV (equivalent)
  IGS_DASHBOARD_EXPORT=1
  IGS_DASHBOARD_OUTPUT_DIR=dashboard_data
  IGS_DASHBOARD_DRY_RUN=1
  IGS_DASHBOARD_MODE=pipeline-dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_exporter as px  # noqa: E402
import dashboard_contract as contract  # noqa: E402


# ==========================================================================
# ReportBundle assembly
# ==========================================================================
def collect_daily_report_data(
    *,
    mode: str,
    business_date: str,
    confirm_safe_run: bool = False,
    report_bundle: dict | None = None,
) -> dict:
    """
    Return a ReportBundle: a plain dict of the SAME computed DataFrames the
    email uses (captured before df.to_html()). This function performs NO
    email side effects and — critically — NEVER recomputes the pipeline.

    mode == 'direct-live':
        Use a caller-supplied `report_bundle` that was handed straight from
        the email calc layer (the SAME objects capture would serialize). This
        function does NOT instantiate RiskStats or run any SQL/API/pricing —
        the calc has already run once for the email. Requires
        confirm_safe_run=True. Refuses (empty bundle + note) otherwise or if
        no bundle was supplied.

    mode == 'artifact-live':
        NOT handled here. The default production path is the fail-closed
        finalizer (dashboard_adapter/finalize_dashboard_run.py), which reads
        the structured artifacts written by the daily run. This exporter is
        the in-memory sibling only; it deliberately refuses to fabricate a
        live bundle by recomputing.

    mode == 'pipeline-dry-run' / 'sample':
        Build the bundle from the built-in sample dataset — no DB, no APIs.
    """
    if mode == "direct-live":
        if not confirm_safe_run:
            return _empty_bundle(
                "Refused direct-live: safe-run not confirmed "
                "(pass --confirm-safe-run)."
            )
        if not report_bundle:
            return _empty_bundle(
                "Refused direct-live: no in-memory report_bundle supplied. "
                "direct-live must receive the already-computed objects from "
                "the email calc layer; it never recomputes. Use artifact-live "
                "+ finalize_dashboard_run.py for the default production path."
            )
        return _adopt_report_bundle(report_bundle)
    if mode == "artifact-live":
        return _empty_bundle(
            "artifact-live is handled by finalize_dashboard_run.py (reads "
            "captured artifacts). export_dashboard.py does not recompute live "
            "data."
        )
    # dry-run and sample both use sample data as DataFrames
    return _collect_sample_bundle(business_date)


def _empty_bundle(note: str) -> dict:
    return {
        "slippage_summary": None, "slippage_algos": [], "alerts": None,
        "zscores": {}, "stop_loss": None, "price_cost_drift": None,
        "exposure": None, "_notes": [note],
    }


# Canonical ReportBundle keys the exporter understands.
_BUNDLE_KEYS = (
    "slippage_summary", "slippage_algos", "alerts", "zscores",
    "stop_loss", "price_cost_drift", "exposure",
)


def _adopt_report_bundle(report_bundle: dict) -> dict:
    """Adopt an in-memory ReportBundle handed from the email calc layer.

    This is the direct-live seam. It performs NO computation: it only shapes
    the caller's already-computed objects into the exporter's bundle dict.
    The caller is responsible for having run the calc exactly once (for the
    email) and passing those SAME objects here.
    """
    bundle = _empty_bundle("direct-live: adopted in-memory ReportBundle "
                           "from the email calc layer (no recomputation).")
    for k in _BUNDLE_KEYS:
        if k in report_bundle and report_bundle[k] is not None:
            bundle[k] = report_bundle[k]
    extra_notes = report_bundle.get("_notes")
    if isinstance(extra_notes, list):
        bundle["_notes"].extend(extra_notes)
    return bundle


def _collect_sample_bundle(business_date: str) -> dict:
    """Build a ReportBundle of DataFrames from the built-in sample payload."""
    import pandas as pd  # type: ignore
    from sample_data import build_sample_payload  # local module

    sp = build_sample_payload(business_date)

    def _df(records):
        return pd.DataFrame(records) if records else None

    # Convert sample contract records back into pipeline-column DataFrames so
    # the SAME exporter mapping is exercised end-to-end.
    slip_summary = _df([{
        "Algo_id": r.get("algoId"), "Algo_name": r.get("algoName"),
        "slippage_model_igs": r.get("slippageModelIgsPct"),
        "slippage_close_price": r.get("slippageClosePricePct"),
        "slippage_cumulative_igs_daily_close": r.get("cumulativeDailyClosePct"),
        "slippage_cumulative_igs_model_close": r.get("cumulativeModelClosePct"),
    } for r in sp["slippage"]["summary"]])

    slip_algos = []
    for a in sp["slippage"]["algos"]:
        best = _df([{"symbol": s["symbol"], "CorpName": s["name"],
                     "Slippage_PnL_₹": s["slippagePnlRs"], "Slippage_pct": s["slippagePct"]}
                    for s in a.get("bestStocks", [])])
        worst = _df([{"symbol": s["symbol"], "CorpName": s["name"],
                      "Slippage_PnL_₹": s["slippagePnlRs"], "Slippage_pct": s["slippagePct"]}
                     for s in a.get("worstStocks", [])])
        dd = _df([{"Date": d["date"], "Slippage_pct": d["slippagePct"]}
                  for d in a.get("dateSeries", [])])
        slip_algos.append({"algoId": a.get("algoId"), "algoName": a.get("algoName"),
                           "headlines": a.get("headlines", []),
                           "best5": best, "worst5": worst, "date_dist": dd})

    alerts = _df([{"Alert Type": r["alertType"], "Metric": r["metric"],
                   "Current Value": r["currentValue"], "Threshold": r["threshold"],
                   "Breach?": r["breach"], "Action Required": r["actionRequired"],
                   "severity": r.get("severity", "")} for r in sp["risk"]["alerts"]])
    stoploss = _df([{"symbol": r["symbol"], "Name": r["name"], "reset_price": r["resetPrice"],
                     "last_price": r["lastPrice"], "Chg%": r["chgPct"], "Days Held": r["daysHeld"],
                     "exec_weight%": r["execWeightPct"], "pct_change%": r["pctChangePct"],
                     "sl_hit": r["slHit"]} for r in sp["risk"]["stopLossWatch"]])
    drift = _df([{"algoName": r["algoName"], "symbol": r["symbol"], "Name": r["name"],
                  "reset_price": r["resetPrice"], "Avg Cost": r["avgCost"],
                  "Diff_ResetPrice_AvgPrice": r["diffResetPriceAvgPricePct"],
                  "exec_weight%": r["execWeightPct"], "Gain/Loss%": r["gainLossPct"]}
                 for r in sp["risk"]["priceCostDrift"]])
    exposure = _df([{"algoName": r["algoName"], "OSID": r["osid"], "Quantity": r["quantity"],
                     "AvgPrice": r["avgPrice"], "MarketPrice": r["marketPrice"], "Isin": r["isin"],
                     "exec_weight%": r["execWeightPct"], "Gain/Loss%": r["gainLossPct"],
                     "MarketValue": r["marketValue"], "symbol": r["symbol"], "coname": r["coname"]}
                    for r in sp["risk"]["exposure"]])

    return {
        "slippage_summary": slip_summary, "slippage_algos": slip_algos,
        "alerts": alerts, "zscores": sp["risk"].get("zScores", {}),
        "stop_loss": stoploss, "price_cost_drift": drift, "exposure": exposure,
        "_notes": [f"sample/dry-run bundle for {business_date} (no DB, no APIs, no email)"],
    }


# ==========================================================================
# Email pass-through (UNCHANGED behaviour)
# ==========================================================================
def send_existing_email(bundle: dict) -> None:
    """
    Intentionally a NO-OP marker.

    The production email is generated and sent by the EXISTING, UNMODIFIED
    pipeline scripts (main.py -> send_alerts_mail.py, slippage_calc.py, etc.).
    This dashboard entry point never sends, alters, re-formats, or re-routes
    that email. Kept here only to make the sibling contract explicit.
    """
    return None


# ==========================================================================
# Dashboard export (the sibling)
# ==========================================================================
def export_dashboard_payload(
    bundle: dict,
    *,
    output_dir: str,
    business_date: str,
    mode: str,
    also_dated: bool = True,
) -> list[str]:
    entry = {
        "direct-live": "collect_daily_report_data(direct-live in-memory bundle) [sibling of email]",
        "artifact-live": "finalize_dashboard_run.py (artifact consumer)",
        "pipeline-dry-run": "collect_daily_report_data(dry-run sample DataFrames)",
        "sample": "built-in sample dataset",
    }.get(mode, mode)

    payload = px.build_payload_from_bundle(
        bundle,
        business_date=business_date,
        mode=mode,
        pipeline_entry_point=entry,
        input_files=["<in-memory pipeline DataFrames>"] if mode == "direct-live"
        else ["<built-in sample>"],
        notes=bundle.get("_notes", []),
    )
    out_path = os.path.join(output_dir, "latest.json")
    return px.write_payload(payload, out_path, also_dated=also_dated, validate=True)


# ==========================================================================
# CLI / env
# ==========================================================================
def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip() in ("1", "true", "TRUE", "yes")


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IGS dashboard sibling exporter (no email side effects).")
    p.add_argument("--dashboard-export", action="store_true",
                   help="Enable dashboard export (else honours IGS_DASHBOARD_EXPORT).")
    p.add_argument("--dashboard-output-dir", default=os.environ.get("IGS_DASHBOARD_OUTPUT_DIR", "dashboard_data"))
    p.add_argument("--dry-run", action="store_true", help="Force dry-run (sample DataFrames, no DB).")
    p.add_argument("--no-email", action="store_true", help="Documentation flag; this entry never emails anyway.")
    p.add_argument("--business-date", default=None)
    p.add_argument("--mode", choices=list(contract.SOURCE_MODES), default=None)
    p.add_argument("--confirm-safe-run", "--confirm-live", dest="confirm_safe_run",
                   action="store_true",
                   help="Required to allow direct-live in-memory bundle export.")
    p.add_argument("--no-dated-copy", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    export_enabled = args.dashboard_export or _env_bool("IGS_DASHBOARD_EXPORT")
    if not export_enabled:
        print("[export_dashboard] export not enabled "
              "(pass --dashboard-export or set IGS_DASHBOARD_EXPORT=1). "
              "Email pipeline is unaffected. Nothing to do.")
        return 0

    business_date = args.business_date or _dt.date.today().isoformat()

    # Resolve mode. Safe default is ALWAYS offline (pipeline-dry-run/sample).
    if args.mode:
        mode = args.mode
    elif args.dry_run or _env_bool("IGS_DASHBOARD_DRY_RUN"):
        mode = "pipeline-dry-run"
    else:
        mode = os.environ.get("IGS_DASHBOARD_MODE", "pipeline-dry-run")
    if mode not in contract.SOURCE_MODES:
        mode = "pipeline-dry-run"

    # Live-mode gating from the CLI. direct-live cannot be driven from the CLI
    # (it needs an in-memory bundle from the calc layer); artifact-live is the
    # finalizer's job. Steer both to the correct entry point and fail closed.
    if mode == "direct-live":
        print("[export_dashboard] direct-live is a library entry point only: "
              "call collect_daily_report_data(mode='direct-live', "
              "report_bundle=<objects from email calc>, confirm_safe_run=True) "
              "from within the pipeline process. Refusing from CLI.")
        return 2
    if mode == "artifact-live":
        print("[export_dashboard] artifact-live is handled by "
              "finalize_dashboard_run.py, which reads captured artifacts and "
              "fails closed. Run: python -m dashboard_adapter.finalize_dashboard_run "
              "--mode artifact-live --confirm-live. Refusing here.")
        return 2
    if mode == "pipeline-live":
        # pipeline-live implies live DB/API access. export_dashboard.py is the
        # OFFLINE sibling and deliberately never touches DB/APIs/email, so it
        # must NOT silently fall through to sample data under a 'live' label.
        # Live data reaches the dashboard ONLY via the in-process direct-live
        # ReportBundle seam or the artifact-live finalizer. Fail closed.
        print("[export_dashboard] pipeline-live is not runnable from this "
              "offline exporter (it never connects to DB/APIs). For live data "
              "use the in-process direct-live seam "
              "(collect_daily_report_data(mode='direct-live', report_bundle=...)) "
              "or capture artifacts + finalize_dashboard_run.py --mode "
              "artifact-live. Refusing here to avoid mislabeling sample data as "
              "live.")
        return 2

    print(f"[export_dashboard] mode={mode} business_date={business_date} "
          f"output_dir={args.dashboard_output_dir} (email untouched)")

    bundle = collect_daily_report_data(
        mode=mode, business_date=business_date, confirm_safe_run=args.confirm_safe_run)
    send_existing_email(bundle)  # explicit no-op

    written = export_dashboard_payload(
        bundle, output_dir=args.dashboard_output_dir, business_date=business_date,
        mode=mode, also_dated=not args.no_dated_copy)
    for w in written:
        print(f"[export_dashboard] wrote {w}")
    for n in bundle.get("_notes", []):
        print(f"[export_dashboard] note: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
