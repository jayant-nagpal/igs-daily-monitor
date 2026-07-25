"""
Producer-regression test: the dashboard sibling capture must reproduce the
SAME numeric values the email renders — no drift, no rounding surprises,
no fabricated rows.

Strategy (offline, no DB): build known producer DataFrames with the exact
columns the real producers hand to the exporter, run them through the
exporter's build_payload_from_bundle, and assert the emitted numbers equal
the inputs. This is the contract the seam captures rely on.

Run: python3 tests/test_producer_regression.py
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard_adapter"))

import pandas as pd
import pipeline_exporter as px


def _bundle():
    return {
        "slippage_summary": pd.DataFrame({
            "Algo_id": [24], "Algo_name": ["ALGO-A"],
            "slippage_model_igs": [12.34], "slippage_close_price": [5.67],
            "slippage_cumulative_igs_daily_close": [-1.5],
            "slippage_cumulative_igs_model_close": [2.25],
        }),
        "slippage_algos": [],
        "alerts": pd.DataFrame({
            "algo_name": ["ALGO-B"], "Symbol": ["AAA"], "metric": ["exposure"],
            "threshold": [5.0], "current_value": [6.1],
            "description": ["over threshold"],
        }),
        "zscores": {"composite": 1.23, "alpha": -0.45, "combined": 0.78},
        "stop_loss": pd.DataFrame({
            "symbol": ["CCC"], "Name": ["Gamma"], "reset_price": [100.0],
            "last_price": [92.0], "Chg%": [-8.0], "sl_hit": [True],
            "algoName": ["ALGO-A"],
        }),
        # price_cost_drift: the CORRECTED tracking_error shape
        "price_cost_drift": pd.DataFrame({
            "algoName": ["ALGO-B2"], "symbol": ["DDD"], "Name": ["Delta"],
            "reset_price": [250.5], "Avg Cost": [240.0],
            "Diff_ResetPrice_AvgPrice": [-4.19],
            "exec_weight%": [1.1], "Gain/Loss%": [3.3],
        }),
        # exposure: lowercase symbol/coname (post case-fix)
        "exposure": pd.DataFrame({
            "algoName": ["ALGO-B"], "symbol": ["AAA"], "coname": ["Alpha"],
            "AvgPrice": [108.0], "Gain/Loss%": [-2.5],
        }),
    }


def test_drift_numbers_survive_unchanged():
    payload = px.build_payload_from_bundle(_bundle(), business_date="2026-07-15",
                                           mode="pipeline-dry-run")
    drift = payload["risk"]["priceCostDrift"]
    assert len(drift) == 1, f"expected exactly 1 drift row, got {len(drift)}"
    row = drift[0]
    assert row["algoName"] == "ALGO-B2"
    assert row["symbol"] == "DDD"
    assert abs(row["resetPrice"] - 250.5) < 1e-9
    assert abs(row["avgCost"] - 240.0) < 1e-9
    assert abs(row["diffResetPriceAvgPricePct"] - (-4.19)) < 1e-9


def test_exposure_symbol_coname_populated():
    payload = px.build_payload_from_bundle(_bundle(), business_date="2026-07-15",
                                           mode="pipeline-dry-run")
    exp = payload["risk"]["exposure"]
    assert len(exp) == 1
    assert exp[0]["symbol"] == "AAA", "case-fix must populate symbol"
    assert exp[0]["coname"] == "Alpha", "case-fix must populate coname"
    assert abs(exp[0]["avgPrice"] - 108.0) < 1e-9


def test_no_rows_fabricated_from_empty():
    b = _bundle()
    b["price_cost_drift"] = pd.DataFrame(
        columns=["algoName", "symbol", "Name", "reset_price", "Avg Cost",
                 "Diff_ResetPrice_AvgPrice", "exec_weight%", "Gain/Loss%"])
    payload = px.build_payload_from_bundle(b, business_date="2026-07-15",
                                           mode="pipeline-dry-run")
    assert payload["risk"]["priceCostDrift"] == [], "empty in -> empty out"


def test_payload_is_strict_json_finite():
    import json
    payload = px.build_payload_from_bundle(_bundle(), business_date="2026-07-15",
                                           mode="pipeline-dry-run")
    # allow_nan=False raises if any NaN/Inf leaked in.
    json.dumps(payload, allow_nan=False)


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
    print(f"\n{passed}/{len(fns)} producer-regression tests passed")
    sys.exit(0 if passed == len(fns) else 1)
