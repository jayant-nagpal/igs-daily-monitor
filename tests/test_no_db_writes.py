"""
Tests for the no-DB-write gate (WS3): IGS_NO_DB_WRITES.

The gate is the single switch the calc producers (slippage, stop-loss) consult
before any to_sql()/INSERT/UPDATE. Default off -> production behaviour
unchanged; a range of truthy spellings enable it.

No DB, no email, no network.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "pythonbatchscripts"))

# dashboard_capture lives in the producer tree (pythonbatchscripts/) and ships
# as dashboard_capture.py.NEW in the producer patch set. In a checkout without
# that tree it is absent -> skip rather than fail.
dc = pytest.importorskip("dashboard_capture")


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "Yes", "on", "On"])
def test_gate_enabled_for_truthy(monkeypatch, val):
    monkeypatch.setenv("IGS_NO_DB_WRITES", val)
    assert dc.no_db_writes_enabled() is True


@pytest.mark.parametrize("val", ["", "0", "false", "no", "off", "  "])
def test_gate_disabled_otherwise(monkeypatch, val):
    monkeypatch.setenv("IGS_NO_DB_WRITES", val)
    assert dc.no_db_writes_enabled() is False


def test_gate_default_off(monkeypatch):
    monkeypatch.delenv("IGS_NO_DB_WRITES", raising=False)
    assert dc.no_db_writes_enabled() is False
