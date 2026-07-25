"""
Offline test for the live_producer section mappers (no DB, no network).

Builds a fake RiskStats object exposing the same frames the real one holds
(riskapi_port_pos, AlertsAlgos(), historical_prices_analysis()) and asserts the
producer's mappers populate exposure / stop_loss / price_cost_drift / alerts
with REAL values that survive the exporter contract.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard_adapter"))

import pandas as pd
import live_producer as lp
import pipeline_exporter as px


class _FakeRisk:
    """Mimics the shape of RiskStats after __init__ (live frames already pulled)."""
    def __init__(self):
        # Live RiskAPI positions: two winners, one big loser (-15%).
        self.riskapi_port_pos = pd.DataFrame({
            "portfolioId": [24, 24, 85],
            "Symbol": ["AAA", "BBB", "CCC"],
            "CompanyName": ["Alpha", "Beta", "Gamma"],
            "Osid": [1001, 1002, 1003],
            "Quantity": [100, 50, 200],
            "AvgPrice": [100.0, 200.0, 300.0],
            "MarketPrice": [110.0, 220.0, 255.0],   # +10%, +10%, -15%
            "MarketValue": [11000.0, 11000.0, 51000.0],
            "pctGain": [0.10, 0.10, -0.15],
            "pctPortfolio": [15.0, 15.0, 70.0],
        })

    def AlertsAlgos(self):
        return pd.DataFrame({
            "portfolioId": [24], "algo_name": ["ALGO-A"],
            "metric": ["pctInvested"], "threshold": [80.0],
            "current_value": [92.0], "description": ["over invested"],
        })

    def historical_prices_analysis(self, historical_days_req=10):
        return pd.DataFrame({
            "Symbol": ["CCC"], "CompanyName": ["Gamma"], "OSID": [1003],
            "portfolioId": [85], "metric": ["min_ret"],
            "threshold": [-0.10], "current_value": [-0.18],
            "description": ["min return breach"],
        })


def _run():
    notes = []
    bundle = {
        "slippage_summary": None, "slippage_algos": [], "alerts": None,
        "zscores": {}, "stop_loss": None, "price_cost_drift": None,
        "exposure": None, "_notes": notes,
    }
    risk = _FakeRisk()
    # step 1: alerts
    aa = risk.AlertsAlgos()
    bundle["alerts"] = lp._algo_alerts_to_contract(aa)
    # step 2: positions -> exposure / drift / stop_loss
    lp._map_positions(bundle, risk, notes)
    # step 3: osid breaches merged into alerts
    lp._merge_osid_alerts(bundle, risk.historical_prices_analysis(), notes)
    return bundle, notes


def test_sections_populate_through_exporter():
    bundle, notes = _run()
    payload = px.build_payload_from_bundle(bundle, business_date="2026-07-23",
                                           mode="pipeline-live")
    risk = payload["risk"]

    # exposure: 3 positions, largest MarketValue first (CCC = 51000)
    assert len(risk["exposure"]) == 3, risk["exposure"]
    assert risk["exposure"][0]["symbol"] == "CCC"
    assert abs(risk["exposure"][0]["marketValue"] - 51000.0) < 1e-6
    assert risk["exposure"][0]["coname"] == "Gamma"

    # price_cost_drift: 3 rows, biggest |diff| first (CCC = -15%)
    assert len(risk["priceCostDrift"]) == 3, risk["priceCostDrift"]
    top = risk["priceCostDrift"][0]
    assert top["symbol"] == "CCC"
    assert abs(top["diffResetPriceAvgPricePct"] - (-15.0)) < 1e-6

    # stop_loss: only the -15% position breaches the -10% floor
    assert len(risk["stopLossWatch"]) == 1, risk["stopLossWatch"]
    sl = risk["stopLossWatch"][0]
    assert sl["symbol"] == "CCC"
    assert abs(sl["chgPct"] - (-15.0)) < 1e-6
    assert sl["slHit"] is True

    # alerts: 1 algo-level + 1 stock-level = 2, with real metric/current/threshold
    assert len(risk["alerts"]) == 2, risk["alerts"]
    metrics = {a["metric"] for a in risk["alerts"]}
    assert any("pctInvested" in m for m in metrics)
    assert any("CCC" in m for m in metrics)  # symbol-prefixed stock breach
    for a in risk["alerts"]:
        assert a["currentValue"] is not None
        assert a["threshold"] is not None
        assert a["breach"] == "Yes"


def test_zscores_map_through_exporter():
    """The legacy pipeline DOES compute z-scores (algo_alerts/zscore.py::
    zscore_calc); the producer wires them in as composite/alpha/combined.
    Prove a populated bundle maps cleanly through the exporter contract."""
    bundle, notes = _run()
    bundle["zscores"] = {"composite": 3.61, "alpha": 1.24, "combined": 2.43}
    payload = px.build_payload_from_bundle(bundle, business_date="2026-07-23",
                                           mode="pipeline-live")
    z = payload["risk"]["zScores"]
    assert z == {"composite": 3.61, "alpha": 1.24, "combined": 2.43}, z


def test_zscores_num_or_none_drops_non_finite():
    """_num_or_none coerces to finite float or None so NaN/inf/str scalars from
    zscore_calc can never poison the strict-JSON contract."""
    assert lp._num_or_none(3.61) == 3.61
    assert lp._num_or_none("2.43") == 2.43
    assert lp._num_or_none(None) is None
    assert lp._num_or_none("n/a") is None
    assert lp._num_or_none(float("nan")) is None
    assert lp._num_or_none(float("inf")) is None


def test_strict_json_finite():
    import json
    bundle, _ = _run()
    payload = px.build_payload_from_bundle(bundle, business_date="2026-07-23",
                                           mode="pipeline-live")
    json.dumps(payload, allow_nan=False)  # raises on NaN/Inf


def test_duplicate_index_positions_do_not_crash():
    """Regression: the real riskapi_port_pos is built via repeated DataFrame.append
    (one block per algo), so its index has DUPLICATE labels. The earlier mapper
    did .reindex(sorted_index) which raised
    'cannot reindex on an axis with duplicate labels' on the live Mac run.
    This reproduces that exact shape and asserts the sections still populate."""
    risk = _FakeRisk()
    # Force a duplicated, non-unique index like the live append() path produces.
    risk.riskapi_port_pos.index = [0, 1, 0]
    assert not risk.riskapi_port_pos.index.is_unique  # precondition

    notes = []
    bundle = {
        "slippage_summary": None, "slippage_algos": [], "alerts": None,
        "zscores": {}, "stop_loss": None, "price_cost_drift": None,
        "exposure": None, "_notes": notes,
    }
    lp._map_positions(bundle, risk, notes)

    # No mapping-failure note, and all three sections built.
    assert not any("positions mapping failed" in n for n in notes), notes
    assert bundle["exposure"] is not None and len(bundle["exposure"]) == 3
    assert bundle["price_cost_drift"] is not None and len(bundle["price_cost_drift"]) == 3
    assert bundle["stop_loss"] is not None and len(bundle["stop_loss"]) == 1

    # Ordering still correct (largest MarketValue / |diff| first = CCC).
    exp = bundle["exposure"].reset_index(drop=True)
    assert exp.loc[0, "symbol"] == "CCC"


def test_live_algo_catalog_names_flow_to_filters():
    """Position sections use the current live catalogue, not a fixed UI map."""
    risk = _FakeRisk()
    notes = []
    bundle = {
        "slippage_summary": None, "slippage_algos": [], "alerts": None,
        "zscores": {}, "stop_loss": None, "price_cost_drift": None,
        "exposure": None, "_notes": notes,
    }
    lp._map_positions(
        bundle, risk, notes,
        algo_names={24: "Live Growth", 85: "Live Defensive"},
    )

    assert set(bundle["price_cost_drift"]["algoName"]) == {
        "Live Growth", "Live Defensive",
    }
    assert set(bundle["exposure"]["algoName"]) == {
        "Live Growth", "Live Defensive",
    }


def test_live_algo_catalog_names_flow_to_alerts():
    risk = _FakeRisk()
    alerts = lp._algo_alerts_to_contract(
        risk.AlertsAlgos(), {24: "Current RiskAPI Name"})
    assert alerts.iloc[0]["Metric"].startswith("Current RiskAPI Name — ")


def test_rebalance_anchor_precedence():
    """Anchor resolver: env var wins; otherwise authoritative FutFlag lookup;
    otherwise a clear error. Never a hardcoded date."""
    import os, datetime as _dt
    import importlib
    import pytest
    sys.path.insert(0, str(REPO / "pythonbatchscripts"))
    sys.path.insert(0, str(REPO / "pythonbatchscripts" / "algo_alerts"))
    try:
        sc = importlib.import_module("slippage_calc")
    except Exception as e:
        # slippage_calc pulls the full runtime stack (utils package, config,
        # matplotlib) that only exists in the Mac venv. Skip cleanly elsewhere;
        # the resolver logic itself is exercised on the Mac.
        pytest.skip(f"slippage_calc import unavailable in this env: {e}")

    # 1. Env var override wins.
    os.environ["IGS_REBALANCE_DATE"] = "2026-07-01"
    try:
        assert sc._resolve_rebalance_anchor() == _dt.date(2026, 7, 1)
    finally:
        os.environ.pop("IGS_REBALANCE_DATE", None)

    # 2. No env + no engine -> clear error (no hardcoded fallback).
    with pytest.raises(RuntimeError):
        sc._resolve_rebalance_anchor(engine=None)

    # 3. Authoritative lookup path returns the fake FutFlag date.
    class _FakeEngine: ...
    def _fake_lookup(engine, on_or_before=None):
        return _dt.date(2026, 6, 30)
    orig = sc._lookup_last_rebalance_date
    sc._lookup_last_rebalance_date = _fake_lookup
    try:
        assert sc._resolve_rebalance_anchor(engine=_FakeEngine()) == _dt.date(2026, 6, 30)
    finally:
        sc._lookup_last_rebalance_date = orig

    # 4. An operator override may never point after the order date.
    os.environ["IGS_REBALANCE_DATE"] = "2026-07-24"
    try:
        with pytest.raises(RuntimeError, match="after the slippage order date"):
            sc._resolve_rebalance_anchor(
                engine=None, on_or_before=_dt.date(2026, 7, 23))
    finally:
        os.environ.pop("IGS_REBALANCE_DATE", None)


def test_non_rebalance_day_with_no_flag_row_is_safe():
    """A normal day need not have a FutFlag row; it must mean False, not abort
    the complete slippage section."""
    import importlib
    import pytest
    sys.path.insert(0, str(REPO / "pythonbatchscripts"))
    sys.path.insert(0, str(REPO / "pythonbatchscripts" / "algo_alerts"))
    try:
        sc = importlib.import_module("slippage_calc")
    except Exception as e:
        pytest.skip(f"slippage_calc import unavailable in this env: {e}")

    original = sc.pd.read_sql
    sc.pd.read_sql = lambda *args, **kwargs: pd.DataFrame(columns=["execution"])
    try:
        assert sc.check_rebalance_flag("2026-07-23", object()) is False
    finally:
        sc.pd.read_sql = original


def test_slippage_diff_object_dtype_ranks_safely():
    """Regression: slippage best5/worst5 rank an aggregated 'diff' column with
    nsmallest/nlargest. LEFT JOINs can leave 'diff' as object dtype (mixed
    None/str), which raises TypeError: "cannot use method 'nsmallest' with this
    dtype". The producer coerces with pd.to_numeric(...).fillna(0.0) first.
    This test reproduces the object-dtype frame and asserts the coercion makes
    ranking succeed."""
    import pandas as pd

    # Aggregated per-symbol frame with an object 'diff' (as seen live).
    sym_pnl = pd.DataFrame({
        "symbol": ["AAA", "BBB", "CCC", "DDD"],
        "CorpName": ["A Ltd", "B Ltd", "C Ltd", "D Ltd"],
        "diff": ["-100.5", None, "250.0", "0"],  # object dtype
    })
    # Non-numeric dtype (pandas reports 'object' or 'str' depending on version).
    assert not pd.api.types.is_numeric_dtype(sym_pnl["diff"])

    # Without coercion this raises TypeError.
    import pytest
    with pytest.raises(TypeError):
        sym_pnl.nsmallest(5, "diff")

    # The producer's fix: coerce to numeric, nulls -> 0.0.
    sym_pnl["diff"] = pd.to_numeric(sym_pnl["diff"], errors="coerce").fillna(0.0)
    worst5 = sym_pnl.nsmallest(5, "diff")
    best5 = sym_pnl.nlargest(5, "diff")

    # Ranking now works and is ordered by numeric value.
    assert list(worst5["symbol"])[0] == "AAA"   # -100.5 is the worst
    assert list(best5["symbol"])[0] == "CCC"    # 250.0 is the best


def test_empty_slippage_frame_can_be_ranked():
    """An empty cumulative query has no derived diff column in production.
    The empty typed ranking frame must still support nsmallest/nlargest."""
    sym_pnl = pd.DataFrame({
        "symbol": pd.Series(dtype="object"),
        "CorpName": pd.Series(dtype="object"),
        "diff": pd.Series(dtype="float64"),
        "Slippage_pct": pd.Series(dtype="object"),
    })
    assert sym_pnl.nsmallest(5, "diff").empty
    assert sym_pnl.nlargest(5, "diff").empty


def test_zscore_nifty_read_is_bounded_and_retried(monkeypatch):
    """The 08S01/10060 live failure retries once with a fresh engine, and SQL
    filters dates at source rather than downloading the full table."""
    import importlib
    import pytest
    sys.path.insert(0, str(REPO / "pythonbatchscripts"))
    sys.path.insert(0, str(REPO / "pythonbatchscripts" / "algo_alerts"))
    try:
        zs = importlib.import_module("zscore")
    except Exception as e:
        pytest.skip(f"zscore import unavailable in this env: {e}")

    engines = [type("E", (), {"dispose": lambda self: None})(),
               type("E", (), {"dispose": lambda self: None})()]
    monkeypatch.setattr(zs.generic, "get_engine", lambda alias: engines.pop(0))
    calls = []

    def fake_read_sql(query, engine):
        calls.append(query)
        if len(calls) == 1:
            raise RuntimeError("08S01 TCP Provider 10060 SQLGetData")
        return pd.DataFrame({"Date": [], "Close": []})

    monkeypatch.setattr(zs.pd, "read_sql", fake_read_sql)
    result = zs._read_nifty_history("2019-11-22", "2026-07-23")
    assert result.empty
    assert len(calls) == 2
    assert "Date >= '2019-11-22'" in calls[0]
    assert "Date <= '2026-07-23'" in calls[0]
    assert float(worst5.iloc[0]["diff"]) == -100.5


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__); passed += 1
        except Exception:
            print("FAIL", fn.__name__); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} live-producer mapping tests passed")
    sys.exit(0 if passed == len(fns) else 1)
