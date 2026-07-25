"""
live_producer.py — READ-ONLY live dashboard producer.

Purpose
-------
Produce today's REAL `latest.json` for the IGS Daily Monitor dashboard by
computing the dashboard bundle from the live sources — WITHOUT running the
legacy `algo_alerts.main` orchestrator (which writes rows back to SQL via
`to_sql` and sends alert emails). This module:

  * Instantiates the EXISTING, UNMODIFIED read-only compute classes
    (RiskStats / DataSources / slippage_calc) which use only `pd.read_sql`
    (SELECT) through the SAME shared db_resolver the doctor validated.
  * Assembles an in-memory ReportBundle of DataFrames.
  * Hands that bundle to the existing `export_dashboard` /
    `pipeline_exporter` seam, which maps DataFrames -> contract JSON and
    writes latest.json.

Safety (matches the operator's standing rules)
----------------------------------------------
  * NO DB writes: this module never calls `.to_sql`, INSERT/UPDATE/DELETE.
    It ALSO installs a hard guard that neutralises DataFrame.to_sql for the
    duration of the run (belt-and-suspenders) unless IGS_ALLOW_DB_WRITES=1.
  * NO email: email is already suppressed unless IGS_ALLOW_EMAIL=1; this
    module additionally hard-unsets that gate.
  * Gates: requires IGS_ALLOW_LIVE=1 AND --confirm-live, identical to the
    doctor, so it can never contact prod by accident.
  * Redacted output: prints names/counts only, never rows/secrets/hosts.

NOT RUN in the Linux sandbox — requires physical macOS arm64 + VPN. The
sandbox cannot reach the databases; run this on the Mac.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

try:
    import pandas as pd  # noqa: E402
except Exception:  # pragma: no cover - pandas always present in the venv
    pd = None

# Make the sibling adapter modules importable (they use bare imports).
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import live_config as lc          # noqa: E402


# --------------------------------------------------------------------------
# Hard write-guard: neutralise DataFrame.to_sql for the whole run.
# --------------------------------------------------------------------------
def _install_write_guard() -> None:
    """Make pandas.DataFrame.to_sql a no-op unless writes are explicitly
    allowed. Defence in depth: even if some legacy code path tries to write,
    nothing lands in the database."""
    if os.environ.get("IGS_ALLOW_DB_WRITES", "").strip().lower() in ("1", "true", "yes", "on"):
        return  # operator explicitly allowed writes; do not guard.
    try:
        import pandas as pd  # type: ignore

        def _blocked_to_sql(self, *a, **k):  # noqa: ANN001
            name = a[0] if a else k.get("name", "<unknown>")
            print(f"[live_producer] BLOCKED to_sql -> '{name}' "
                  f"({len(self)} rows NOT written; read-only run)")
            return None

        pd.DataFrame.to_sql = _blocked_to_sql  # type: ignore[assignment]
    except Exception as e:  # pragma: no cover
        print(f"[live_producer] WARN: could not install write guard: {type(e).__name__}")


# --------------------------------------------------------------------------
# Bundle collection — read-only compute from the real sources.
# --------------------------------------------------------------------------
def _collect_live_bundle(business_date: str) -> dict:
    """Compute the dashboard ReportBundle from live read-only sources.

    Each producer is wrapped so one failing section degrades gracefully
    (empty frame + note) instead of aborting the whole dashboard.
    """
    notes: list[str] = []
    bundle: dict = {
        "slippage_summary": None, "slippage_algos": [], "alerts": None,
        "zscores": {}, "stop_loss": None, "price_cost_drift": None,
        "exposure": None, "_notes": notes,
    }

    # In production, the desk's compute modules live under pythonbatchscripts/
    # (proprietary — not included in this public repo) and
    # rely on being importable by their bare names. Add both roots.
    repo_root = _HERE.parent
    algo_dir = repo_root / "pythonbatchscripts" / "algo_alerts"
    for p in (repo_root / "pythonbatchscripts", algo_dir):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)

    # ---- Config resolution (legacy quirk) ---------------------------------
    # utils/config.py: (a) defaults env to 'stage' unless os.environ['env'] is
    # set, and (b) reads config via the RELATIVE path '../config/Config-*.cfg',
    # which only resolves when CWD == algo_alerts/. configparser.read() fails
    # SILENTLY on a bad path, leaving every key None (-> pytz.timezone(None)
    # crash). We force prod and chdir into algo_alerts/ so the relative path
    # resolves, then restore CWD afterwards.
    if not os.environ.get("env"):
        os.environ["env"] = "prod"
        print("[live_producer] set env=prod (was unset; avoids stage config)")
    _prev_cwd = os.getcwd()
    try:
        if algo_dir.is_dir():
            os.chdir(algo_dir)
            print(f"[live_producer] chdir -> algo_alerts/ so ../config/Config-{os.environ['env']}.cfg resolves")
    except Exception as e:
        notes.append(f"chdir to algo_alerts failed: {type(e).__name__}: {e}")

    # ---- RiskStats: alerts, stop-loss watch, price-cost drift, exposure ----
    risk = None
    # Load the current RiskAPI catalogue BEFORE RiskStats is constructed.  The
    # dashboard-only env override makes DataSources pull these live portfolios
    # instead of its legacy email defaults (24/85/187).  The email pipeline
    # never sets this variable and is therefore unchanged.
    os.environ.pop("IGS_DASHBOARD_ALGOS_JSON", None)
    algo_names: dict[int, str] = _load_live_algo_catalog(notes)
    if algo_names:
        os.environ["IGS_DASHBOARD_ALGOS_JSON"] = json.dumps(
            {name: algo_id for algo_id, name in algo_names.items()}
        )
        print(f"[live_producer] RiskStats scope: {len(algo_names)} live algos")
    try:
        import RiskStats as rs  # type: ignore
        print("[live_producer] computing RiskStats (read-only SELECTs)...")
        risk = rs.RiskStats()
    except Exception as e:
        notes.append(f"RiskStats unavailable: {type(e).__name__}: {e}")
        print(f"[live_producer] RiskStats FAILED: {type(e).__name__}: {e}")

    if risk is not None:
        # 1) Algo-level alerts (metric threshold breaches). Already proven live.
        #    Normalize to the exporter's alerts contract columns so the panel
        #    shows metric/current/threshold instead of blanks.
        algo_alerts = _try(notes, "alerts", lambda: risk.AlertsAlgos())
        if algo_alerts is not None and len(algo_alerts):
            bundle["alerts"] = _algo_alerts_to_contract(
                algo_alerts, algo_names)
            print(f"[live_producer] alerts: {len(bundle['alerts'])} rows "
                  f"(algo-level)")

        # 2) Exposure + stop-loss + price/cost drift are all derived from the
        #    live RiskAPI positions/summary frames that RiskStats already pulled in
        #    __init__ (riskapi_port_pos / riskapi_port_stats). These are real position
        #    rows with MarketValue / pctGain / pctPortfolio per algo.
        _map_positions(bundle, risk, notes, algo_names)

        # 3) Stock/OSID-level breaches (a SECOND alerts table, by symbol) from
        #    historical_prices_analysis(). These are threshold breaches, so we
        #    merge them into the alerts section rather than mislabeling them as
        #    exposure/drift.
        osid_frame = _try(notes, "historical_prices_analysis",
                          lambda: risk.historical_prices_analysis())
        if osid_frame is not None and len(osid_frame):
            _merge_osid_alerts(bundle, osid_frame, notes)

        # 4) z-scores: the legacy pipeline DOES compute portfolio return/alpha
        #    z-scores in algo_alerts/zscore.py::zscore_calc(). That function is
        #    pure read-only (SignalStore NAV SELECT + NIFTY50 SELECT via read_sql;
        #    no to_sql, no email) and returns the three final composite scalars.
        #    We call it directly and map its output to the exporter's
        #    composite/alpha/combined contract. It requires CWD == algo_alerts/
        #    for the same config-relative path reason, which holds here.
        def _compute_zscores():
            import zscore as _zs  # type: ignore
            out = _zs.zscore_calc() or {}
            return {
                "composite": _num_or_none(out.get("composite_zscore_lag")),
                "alpha": _num_or_none(out.get("composite_zscore_alpha_lag")),
                "combined": _num_or_none(out.get("composite_zscore_combined")),
            }

        z = _try(notes, "zscores", _compute_zscores)
        if z:
            # Keep only real numeric values; the exporter drops None keys.
            z = {k: v for k, v in z.items() if v is not None}
            if z:
                bundle["zscores"] = z
                print(f"[live_producer] zscores: {len(z)} values "
                      f"(composite/alpha/combined)")
            else:
                notes.append("zscores: computed but all values non-numeric.")

    # Restore original CWD (writing latest.json uses absolute paths anyway).
    try:
        os.chdir(_prev_cwd)
    except Exception:
        pass

    # ---- Slippage summary --------------------------------------------------
    # slippage_calc.compute_slippage_bundle() runs the SAME per-algo math as the
    # email path but sends no email, draws no charts, and builds no HTML — pure
    # read-only SELECTs. We chdir back into algo_alerts/ for the config-relative
    # path, then restore CWD.
    try:
        if algo_dir.is_dir():
            os.chdir(algo_dir)
        import slippage_calc as sc  # type: ignore
        summary_df, algos = sc.compute_slippage_bundle()
        if summary_df is not None and len(summary_df):
            bundle["slippage_summary"] = summary_df
            print(f"[live_producer] slippage_summary: {len(summary_df)} rows")
        if algos:
            bundle["slippage_algos"] = algos
            print(f"[live_producer] slippage_algos: {len(algos)} algos")
    except Exception as e:
        notes.append(f"slippage compute failed: {type(e).__name__}: {e}")
        print(f"[live_producer] slippage FAILED: {type(e).__name__}: {e}")
    finally:
        try:
            os.chdir(_prev_cwd)
        except Exception:
            pass

    return bundle


def _num_or_none(v):
    """Coerce a value to a finite float, or return None. zscore_calc() returns
    Python floats already, but guard against NaN/inf/None/str defensively so a
    bad scalar never poisons the JSON contract."""
    try:
        import math
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _try(notes, label, fn):
    try:
        return fn()
    except Exception as e:
        notes.append(f"{label} failed: {type(e).__name__}: {e}")
        print(f"[live_producer] {label} FAILED: {type(e).__name__}: {e}")
        return None


def _safe_section(bundle, notes, key, fn):
    val = _try(notes, key, fn)
    if val is not None:
        bundle[key] = val
        try:
            n = len(val)
        except Exception:
            n = "?"
        print(f"[live_producer] {key}: {n} rows")


def _colpick(df, *names):
    """Case-insensitive column resolver; returns the actual column name or None."""
    lower = {str(c).lower(): c for c in df.columns}
    for n in names:
        if str(n).lower() in lower:
            return lower[str(n).lower()]
    return None


def _load_live_algo_catalog(notes) -> dict[int, str]:
    """Read the current RiskAPI algo ID/name catalogue through the existing
    resolver-aware, read-only source path."""
    try:
        from utils import generic as ut  # type: ignore
        catalog = ut.get_all_live_algos()
        id_c = _colpick(catalog, "AlgoID")
        name_c = _colpick(catalog, "AlgoName")
        if id_c is None or name_c is None:
            notes.append("live algo catalogue missing AlgoID/AlgoName columns; "
                         "using live IDs as labels.")
            return {}
        result = {}
        for _, row in catalog[[id_c, name_c]].dropna(subset=[id_c]).iterrows():
            try:
                algo_id = int(row[id_c])
            except (TypeError, ValueError):
                continue
            raw_name = row[name_c]
            name = "" if pd.isna(raw_name) else str(raw_name).strip()
            result[algo_id] = name or str(algo_id)
        print(f"[live_producer] algo catalogue: {len(result)} live names")
        return result
    except Exception as e:
        notes.append(f"live algo catalogue unavailable: {type(e).__name__}: {e}; "
                     "using live IDs as labels.")
        print(f"[live_producer] algo catalogue FAILED: {type(e).__name__}: {e}")
        return {}


def _algo_labels(values, algo_names):
    """Map live algo IDs to live names without imposing a fixed allow-list."""
    def label(value):
        try:
            algo_id = int(value)
        except (TypeError, ValueError):
            return str(value)
        return algo_names.get(algo_id, str(algo_id))

    return values.map(label)


def _map_positions(bundle, risk, notes, algo_names=None):
    """Derive exposure / stop_loss / price_cost_drift from the LIVE RiskAPI
    positions frame RiskStats already holds. All read-only; every value comes
    straight from the ExecAPI/RiskAPI response. Output columns are renamed to the exact
    SOURCE names the exporter's df_to_records() mapping expects, so the panels
    populate instead of showing blank cells."""
    try:
        pos = getattr(risk, "riskapi_port_pos", None)
        if pos is None or not len(pos):
            notes.append("positions frame empty — exposure/stop_loss/drift "
                         "not derived.")
            return

        # RiskAPI positions are assembled via repeated DataFrame.append (one block
        # per algo), so the index carries DUPLICATE labels (each algo restarts
        # at 0). Any later .reindex(sorted_index) then fails with
        # "cannot reindex on an axis with duplicate labels". Collapse to a clean
        # unique RangeIndex up front so every downstream sort/reindex is safe.
        pos = pos.copy().reset_index(drop=True)
        sym_c = _colpick(pos, "Symbol", "wonSymbol", "LocalSymbol", "Ticker")
        name_c = _colpick(pos, "CompanyName", "companyName", "coname", "Name")
        osid_c = _colpick(pos, "Osid", "OSID", "CorpOSID")
        isin_c = _colpick(pos, "Isin", "ISIN")
        qty_c = _colpick(pos, "Quantity", "Position", "Shares")
        algo_c = _colpick(pos, "portfolioId", "AlgoID")
        mv_c = _colpick(pos, "MarketValue")
        mp_c = _colpick(pos, "MarketPrice")
        ap_c = _colpick(pos, "AvgPrice")
        gain_c = _colpick(pos, "pctGain")
        pctp_c = _colpick(pos, "pctPortfolio")

        # gain fraction -> percent; ensure a gain column exists
        if not gain_c and mp_c and ap_c:
            pos["pctGain"] = (pos[mp_c] / pos[ap_c]) - 1
            gain_c = "pctGain"
        gain_pct = None
        if gain_c:
            pos["__gainPct"] = pos[gain_c].astype(float) * 100.0
            gain_pct = "__gainPct"

        def col(src):
            return pos[src] if src else None

        # ---------- exposure (per-position, contract source names) ----------
        algo_names = algo_names or {}
        exp = pd.DataFrame()
        if algo_c is not None:
            exp["algoName"] = _algo_labels(col(algo_c), algo_names)
        if osid_c: exp["OSID"] = col(osid_c)
        if qty_c: exp["Quantity"] = col(qty_c)
        if ap_c: exp["AvgPrice"] = col(ap_c)
        if mp_c: exp["MarketPrice"] = col(mp_c)
        if isin_c: exp["Isin"] = col(isin_c)
        if pctp_c is not None: exp["exec_weight%"] = pos[pctp_c]
        if gain_pct: exp["Gain/Loss%"] = pos[gain_pct]
        if mv_c: exp["MarketValue"] = col(mv_c)
        if sym_c: exp["symbol"] = col(sym_c)
        if name_c: exp["coname"] = col(name_c)
        if len(exp.columns):
            exp = exp.reset_index(drop=True)
            if mv_c and "MarketValue" in exp.columns:
                exp["__abs"] = exp["MarketValue"].astype(float).abs()
                exp = exp.sort_values("__abs", ascending=False).drop(columns="__abs")
            bundle["exposure"] = exp
            print(f"[live_producer] exposure: {len(exp)} rows (RiskAPI positions)")

        # ---------- price_cost_drift (contract source names) ----------
        if gain_pct or (mp_c and ap_c):
            drift = pd.DataFrame()
            if algo_c is not None:
                drift["algoName"] = _algo_labels(col(algo_c), algo_names)
            if sym_c: drift["symbol"] = col(sym_c)
            if name_c: drift["Name"] = col(name_c)
            if mp_c: drift["reset_price"] = col(mp_c)   # current mkt price
            if ap_c: drift["Avg Cost"] = col(ap_c)
            if mp_c and ap_c:
                drift["Diff_ResetPrice_AvgPrice"] = (
                    (pos[mp_c].astype(float) / pos[ap_c].astype(float)) - 1
                ) * 100.0
            if pctp_c is not None: drift["exec_weight%"] = pos[pctp_c]
            if gain_pct: drift["Gain/Loss%"] = pos[gain_pct]
            drift = drift.reset_index(drop=True)
            if "Diff_ResetPrice_AvgPrice" in drift.columns:
                drift["__abs"] = drift["Diff_ResetPrice_AvgPrice"].abs()
                drift = drift.sort_values("__abs", ascending=False).drop(columns="__abs")
            bundle["price_cost_drift"] = drift
            print(f"[live_producer] price_cost_drift: {len(drift)} rows")

        # ---------- stop_loss watch (losing positions) ----------
        if gain_pct:
            floor_pct = float(os.environ.get("IGS_STOPLOSS_PCT", "-10"))
            mask = pos[gain_pct].astype(float) <= floor_pct
            sl = pd.DataFrame()
            if sym_c: sl["symbol"] = pos.loc[mask, sym_c]
            if name_c: sl["Name"] = pos.loc[mask, name_c]
            if mp_c: sl["last_price"] = pos.loc[mask, mp_c]
            if ap_c: sl["reset_price"] = pos.loc[mask, ap_c]
            sl["Chg%"] = pos.loc[mask, gain_pct]
            sl["pct_change%"] = pos.loc[mask, gain_pct]
            if pctp_c is not None: sl["exec_weight%"] = pos.loc[mask, pctp_c]
            sl["sl_hit"] = True
            sl = sl.sort_values("Chg%")  # worst first
            bundle["stop_loss"] = sl
            print(f"[live_producer] stop_loss: {len(sl)} rows "
                  f"(Gain/Loss%% <= {floor_pct})")
    except Exception as e:
        notes.append(f"positions mapping failed: {type(e).__name__}: {e}")
        print(f"[live_producer] positions mapping FAILED: {type(e).__name__}: {e}")


def _merge_osid_alerts(bundle, df, notes):
    """Fold symbol-level breaches from historical_prices_analysis() into the
    alerts section, remapped to the alerts contract source columns
    (Metric / Current Value / Threshold / Breach?). Real breaches only."""
    try:
        m_c = _colpick(df, "metric")
        cv_c = _colpick(df, "current_value")
        th_c = _colpick(df, "threshold")
        sym_c = _colpick(df, "Symbol")
        desc_c = _colpick(df, "description")
        if not (m_c and cv_c and th_c):
            notes.append("osid breach frame missing expected columns — skipped.")
            return
        osid = pd.DataFrame()
        # Prefix the metric with the symbol so the alert row is self-describing.
        if sym_c:
            osid["Metric"] = (df[sym_c].astype(str) + " — " + df[m_c].astype(str))
        else:
            osid["Metric"] = df[m_c].astype(str)
        osid["Alert Type"] = "Stock-level breach"
        osid["Current Value"] = df[cv_c]
        osid["Threshold"] = df[th_c]
        osid["Breach?"] = "Yes"
        if desc_c:
            osid["Action Required"] = df[desc_c]
        osid["severity"] = "breach"

        existing = bundle.get("alerts")
        if existing is not None and len(existing):
            # `existing` is already in contract-source form (step 1).
            bundle["alerts"] = pd.concat([existing, osid], ignore_index=True)
        else:
            bundle["alerts"] = osid
        total = len(bundle["alerts"])
        print(f"[live_producer] alerts: {total} rows "
              f"(incl. {len(osid)} stock-level)")
    except Exception as e:
        notes.append(f"osid merge failed: {type(e).__name__}: {e}")
        print(f"[live_producer] osid merge FAILED: {type(e).__name__}: {e}")


def _algo_alerts_to_contract(df, algo_names=None):
    """Rename the AlertsAlgos() frame columns to the alerts contract source
    names so it concatenates cleanly with the OSID breaches."""
    out = pd.DataFrame()
    m_c = _colpick(df, "metric")
    cv_c = _colpick(df, "current_value")
    th_c = _colpick(df, "threshold")
    nm_c = _colpick(df, "algo_name")
    id_c = _colpick(df, "portfolioId", "AlgoID")
    desc_c = _colpick(df, "description")
    if id_c and algo_names and m_c:
        labels = _algo_labels(df[id_c], algo_names)
        out["Metric"] = labels.astype(str) + " — " + df[m_c].astype(str)
    elif nm_c and m_c:
        out["Metric"] = df[nm_c].astype(str) + " — " + df[m_c].astype(str)
    elif m_c:
        out["Metric"] = df[m_c].astype(str)
    out["Alert Type"] = "Algo-level breach"
    if cv_c is not None: out["Current Value"] = df[cv_c]
    if th_c is not None: out["Threshold"] = df[th_c]
    out["Breach?"] = "Yes"
    if desc_c is not None: out["Action Required"] = df[desc_c]
    out["severity"] = "breach"
    return out


# --------------------------------------------------------------------------
# Write latest.json via the existing exporter seam.
# --------------------------------------------------------------------------
def _write_latest(bundle: dict, business_date: str, out_path: str) -> None:
    import pipeline_exporter as px  # noqa: E402
    payload = px.build_payload_from_bundle(
        bundle,
        business_date=business_date,
        mode="artifact-live",
        pipeline_entry_point="live_producer (read-only)",
    )
    import json
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    os.replace(tmp, out_path)  # atomic
    # dated copy alongside
    dated = os.path.join(os.path.dirname(out_path),
                         f"dashboard_payload_{business_date}.json")
    try:
        with open(dated, "w") as f:
            json.dump(payload, f, indent=2, default=str)
    except Exception:
        pass


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def run(confirm_live: bool, business_date: str, out_path: str) -> int:
    # Resolve output to an absolute path NOW, before any chdir in the collector
    # could change what a relative path means.
    out_path = os.path.abspath(out_path)
    # Same gate as the doctor: env + explicit flag.
    if not lc.is_live_allowed() or not confirm_live:
        print("[live_producer] REFUSED: live run requires IGS_ALLOW_LIVE=1 AND --confirm-live.")
        return 2

    # Enforce no-email posture regardless of ambient env.
    os.environ.pop("IGS_ALLOW_EMAIL", None)
    _install_write_guard()

    print(f"[live_producer] env=prod  businessDate={business_date}  "
          f"(READ-ONLY; no DB writes; no email)")
    bundle = _collect_live_bundle(business_date)
    _write_latest(bundle, business_date, out_path)

    notes = bundle.get("_notes") or []
    if notes:
        print("[live_producer] notes:")
        for n in notes:
            print(f"   - {n}")
    print(f"[live_producer] wrote {out_path}")
    # Non-zero only if EVERY data section is empty (nothing to show).
    data_keys = ("slippage_summary", "alerts", "exposure",
                 "stop_loss", "price_cost_drift")
    if all(bundle.get(k) is None for k in data_keys):
        print("[live_producer] WARNING: all data sections empty — see notes above.")
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read-only live dashboard producer.")
    ap.add_argument("--confirm-live", action="store_true",
                    help="Required (with IGS_ALLOW_LIVE=1) to run live read-only probes.")
    ap.add_argument("--business-date", default=_dt.date.today().isoformat(),
                    help="Business date YYYY-MM-DD (default: today).")
    default_out = str(_HERE.parent / "igs-daily-monitor" / "public" / "data" / "latest.json")
    ap.add_argument("--output", default=default_out,
                    help="Destination latest.json path.")
    args = ap.parse_args(argv)
    return run(args.confirm_live, args.business_date, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
