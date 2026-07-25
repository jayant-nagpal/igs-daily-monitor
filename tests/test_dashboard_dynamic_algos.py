"""Dashboard-only algo scope must not alter the legacy email defaults."""
import importlib
import json
import os
import sys
from pathlib import Path

import pytest
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "pythonbatchscripts"))
sys.path.insert(0, str(REPO / "pythonbatchscripts" / "algo_alerts"))


def _module():
    try:
        return importlib.import_module("data_sources")
    except Exception as exc:
        pytest.skip(f"data_sources import unavailable in this env: {exc}")


def test_legacy_algo_defaults_unchanged(monkeypatch):
    ds = _module()
    monkeypatch.delenv("IGS_DASHBOARD_ALGOS_JSON", raising=False)
    monkeypatch.setenv("IGS_EXECAPI_PASSWORD", "offline-test")
    obj = ds.DataSources()
    assert obj.algo_dict == {
        "stoploss_algo_a": 24,
        "stoploss_algo_b": 85,
        "stoploss_algo_b2": 187,
    }


def test_dashboard_algo_scope_comes_from_live_map(monkeypatch):
    ds = _module()
    monkeypatch.setenv("IGS_EXECAPI_PASSWORD", "offline-test")
    monkeypatch.setenv(
        "IGS_DASHBOARD_ALGOS_JSON",
        json.dumps({"Live One": 188, "Live Two": 232}),
    )
    obj = ds.DataSources()
    assert obj.algo_dict == {"Live One": 188, "Live Two": 232}


def test_riskstats_ratios_are_zero_safe():
    """A zero live NAV must not make the complete RiskStats section fail."""
    ds = _module()
    assert np.isnan(ds._safe_ratio(100, 0))
    assert np.isnan(ds._safe_ratio(0, 0))
    assert np.isnan(ds._safe_ratio(100, None))
    assert ds._safe_ratio(100, 25) == 4.0
