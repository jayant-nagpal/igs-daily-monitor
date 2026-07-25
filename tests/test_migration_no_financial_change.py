"""
Migration safety test (Q2 binding requirement):

  Proves the 3.0 -> 4.0 schema bump is PURELY ADDITIVE for financial data:
  every row shape and every financial value present in a 3.0 payload is
  preserved byte-for-byte through adapt_legacy_v3. The adapter may ONLY add
  the new health envelope (pipelineStatus/producerStatus/lastSuccessfulRunAt)
  and a stale/legacy note — it must NOT touch slippage/risk numbers.

Run: python3 tests/test_migration_no_financial_change.py
"""
import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard_adapter"))

import dashboard_contract as contract


def _rich_v3_payload():
    """A 3.0 payload with real financial numbers in every section."""
    return {
        "schemaVersion": "3.0",
        "runId": "legacy-run-1",
        "businessDate": "2026-07-10",
        "generatedAt": "2026-07-10T10:00:00+00:00",
        "source": {"mode": "pipeline-live", "pipelineEntryPoint": "legacy"},
        "slippage": {
            "summary": [
                {"algoName": "ALGO-B", "slippageModelIgs": 12.34,
                 "slippageClosePrice": 5.67, "cumIgsDailyClose": -1.5,
                 "cumIgsModelClose": 2.25},
            ],
            "algos": [
                {"algoName": "ALGO-B", "best5": [
                    {"symbol": "AAA", "name": "Alpha", "slippagePnlRs": 1000.5,
                     "slippagePct": 0.42}],
                 "worst5": [
                    {"symbol": "BBB", "name": "Beta", "slippagePnlRs": -900.25,
                     "slippagePct": -0.31}]},
            ],
        },
        "risk": {
            "alerts": [
                {"algoName": "ALGO-B", "symbol": "AAA", "metric": "exposure",
                 "threshold": 5.0, "currentValue": 6.1,
                 "description": "over threshold"}],
            "zScores": {"composite": 1.23, "alpha": -0.45, "combined": 0.78},
            "stopLossWatch": [
                {"algoName": "ALGO-A", "symbol": "CCC", "resetPrice": 100.0,
                 "lastPrice": 92.0, "chgPct": -8.0, "slHit": True}],
            "priceCostDrift": [
                {"algoName": "ALGO-B2", "symbol": "DDD", "resetPrice": 250.5,
                 "avgCost": 240.0, "diffResetPriceAvgPricePct": -4.19,
                 "execWeightPct": 1.1, "gainLossPct": 3.3}],
            "exposure": [
                {"algoName": "ALGO-B", "symbol": "AAA", "coname": "Alpha",
                 "quantity": 100, "avgPrice": 108.0, "marketValue": 10800.0,
                 "gainLossPct": -2.5}],
        },
        "dataHealth": {"strictJson": True, "warnings": ["legacy warning kept"]},
    }


def _all_financial_blocks(payload):
    """Extract the parts that must NOT change (everything except dataHealth,
    schemaVersion, and source.notes which the adapter is allowed to append)."""
    return {
        "slippage": payload["slippage"],
        "risk": payload["risk"],
        "businessDate": payload["businessDate"],
        "runId": payload["runId"],
        "generatedAt": payload["generatedAt"],
    }


def test_migration_preserves_all_financial_data():
    original = _rich_v3_payload()
    frozen = copy.deepcopy(_all_financial_blocks(original))

    adapted = contract.adapt_legacy_v3(original)

    # 1. schema bumped
    assert adapted["schemaVersion"] == "4.0"

    # 2. EVERY financial block is byte-for-byte identical
    after = _all_financial_blocks(adapted)
    assert after == frozen, "financial data changed during migration!"

    # 3. adapter did not mutate the input in place
    assert _all_financial_blocks(original) == frozen

    # 4. the ONLY additions are the health envelope + a legacy note
    assert adapted["dataHealth"]["pipelineStatus"] == "stale"
    assert adapted["dataHealth"]["lastSuccessfulRunAt"] is None
    assert any("legacy" in n.lower() or "stale" in n.lower()
               for n in adapted["source"].get("notes", []))
    # legacy warning preserved
    assert "legacy warning kept" in adapted["dataHealth"].get("warnings", [])


def test_migrated_payload_is_structurally_valid_4():
    adapted = contract.adapt_legacy_v3(_rich_v3_payload())
    # It should be structurally valid 4.0 (so the reader can display it)...
    problems = contract.validate_structure(adapted)
    assert problems == [], problems
    # ...but MUST NOT be treated as healthy live.
    assert adapted["dataHealth"]["pipelineStatus"] != "ok"


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
    print(f"\n{passed}/{len(fns)} migration tests passed")
    sys.exit(0 if passed == len(fns) else 1)
