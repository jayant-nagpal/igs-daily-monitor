"""
Source-doctor tests (item 6 / item 12).

Every probe is monkeypatched so NO real network / DB connection is ever opened.
Covers all resolver sources, the CERTIFICATE error class, and the gate refusal.
Physical-Mac / real-connection checks are NOT RUN here (require macOS arm64).
"""
import socket
import sys
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dashboard_adapter"))

import live_source_doctor as D  # noqa: E402
import db_resolver as R          # noqa: E402


def _configure_all(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("IGS_") or k.startswith("VITE_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("IGS_ENV", "prod")
    monkeypatch.setenv("IGS_ALLOW_LIVE", "1")
    for pref in ("IGS_POSITIONSDB_", "IGS_POSITIONSDB_DEV_", "IGS_POSITIONSDB_STG_",
                 "IGS_WAREHOUSE_", "IGS_TIMESERIESDB_", "IGS_BACKTESTING_",
                 "IGS_REFDB_", "IGS_SIGNALSTORE_"):
        monkeypatch.setenv(pref + "HOST", "h.example.internal")
        monkeypatch.setenv(pref + "PORT", "1433")
        monkeypatch.setenv(pref + "DATABASE", "db")
        monkeypatch.setenv(pref + "USER", "u")
        monkeypatch.setenv(pref + "PASSWORD", "p")
    monkeypatch.setenv("IGS_EXECAPI_BASE_URL", "https://execapi.example")
    monkeypatch.setenv("IGS_EXECAPI_USER", "au")
    monkeypatch.setenv("IGS_EXECAPI_PASSWORD", "ap")
    monkeypatch.setenv("IGS_RISKAPI_BASE_URL", "https://riskapi.example")


def test_gate_refuses_without_confirm(monkeypatch):
    _configure_all(monkeypatch)
    rc = D.run(confirm_live=False, timeout=1, sources=list(D.REQUIRED_SOURCES))
    assert rc == 2


def test_all_sources_pass_with_mocked_connections(monkeypatch, capsys):
    _configure_all(monkeypatch)

    # Mock the SQL engine connect() and the HTTP calls — NO real connection.
    class _Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **k): return None

    class _Engine:
        def connect(self): return _Conn()

    monkeypatch.setattr(R, "resolve_engine", lambda alias, **k: _Engine())
    monkeypatch.setattr(D, "resolve_engine", lambda *a, **k: _Engine(), raising=False)

    class _Resp:
        status_code = 200

    import requests
    monkeypatch.setattr(requests, "head", lambda *a, **k: _Resp())
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())

    # driver-present check is environment-specific; force it PASS for this dry run
    monkeypatch.setattr(D, "check_sqlserver_driver",
                        lambda: {"name": "sqlserver-driver", "pass": True,
                                 "category": None, "detail": "mocked driver present"})

    rc = D.run(confirm_live=True, timeout=1, sources=list(D.ALL_SOURCES))
    out = capsys.readouterr().out
    # Every source name must appear in the report and none printed a secret host.
    for s in D.ALL_SOURCES:
        assert s in out
    assert "h.example.internal" not in out  # never leak the configured host
    assert rc == 0


def test_probe_db_reports_config_when_missing(monkeypatch):
    _configure_all(monkeypatch)
    # remove refdb config -> CONFIG category, not a crash
    for part in ("HOST", "PORT", "DATABASE", "USER", "PASSWORD"):
        monkeypatch.delenv("IGS_REFDB_" + part, raising=False)
    res = D.probe_source("refdb", timeout=1)
    assert res["pass"] is False
    assert res["category"] == "CONFIG"


def test_certificate_error_class():
    class SSLishError(Exception):
        pass
    exc = SSLishError("certificate verify failed: self signed certificate")
    assert D._categorise(exc) == "CERTIFICATE"


def test_timeout_and_dns_classes():
    assert D._categorise(socket.timeout("timed out")) == "TIMEOUT"
    assert D._categorise(Exception("getaddrinfo failed: name or service not known")) == "VPN_DNS"
    assert D._categorise(Exception("libodbc.so.2: cannot open shared object")) == "DRIVER"
