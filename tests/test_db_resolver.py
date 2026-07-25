"""
Tests for the shared SQLAlchemy resolver (dashboard_adapter/db_resolver.py).

Pure logic / URL-construction tests — these NEVER open a connection and do NOT
require pyodbc / an ODBC system driver, so they run in any environment. Only the
actual driver-present connectivity check is out of scope here (that lives in the
source doctor and is NOT RUN off a physical Mac arm64 host).
"""
import pytest

pytest.importorskip("sqlalchemy")

from dashboard_adapter import db_resolver as R  # noqa: E402


# -------- helper -----------------------------------------------------------
def _clear(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith("IGS_") or k.startswith("VITE_"):
            monkeypatch.delenv(k, raising=False)


# -------- alias -> env mapping --------------------------------------------
def test_legacy_alias_map_is_deterministic():
    assert R.normalize_alias("BackTesting") == "backtesting"
    assert R.normalize_alias("warehouse_server") == "warehouse"
    assert R.normalize_alias("TimeSeriesDB") == "timeseriesdb"
    assert R.normalize_alias("positionsdb") == "positionsdb"
    assert R.normalize_alias("positionsdb_dev") == "positionsdb_dev"
    assert R.normalize_alias("positionsdb_stg") == "positionsdb_stg"
    assert R.normalize_alias("refdb") == "refdb"


def test_unknown_alias_raises():
    with pytest.raises(R.ResolverConfigError):
        R.normalize_alias("no_such_source")


def test_backtesting_alias_maps_to_backtesting_env(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_BACKTESTING_HOST", "bt.example.internal")
    monkeypatch.setenv("IGS_BACKTESTING_PORT", "1433")
    monkeypatch.setenv("IGS_BACKTESTING_DATABASE", "BackTesting")
    monkeypatch.setenv("IGS_BACKTESTING_USER", "svc_ro")
    monkeypatch.setenv("IGS_BACKTESTING_PASSWORD", "p")
    url = R.make_url("BackTesting")  # legacy alias
    assert url.host == "bt.example.internal"
    assert url.port == 1433
    assert url.database == "BackTesting"
    assert url.drivername == "mssql+pyodbc"


# -------- Driver 18 + Encrypt defaults ------------------------------------
def test_sqlserver_driver18_and_tls_defaults(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_POSITIONSDB_HOST", "ocm.example.internal")
    monkeypatch.setenv("IGS_POSITIONSDB_PORT", "1433")
    monkeypatch.setenv("IGS_POSITIONSDB_DATABASE", "PositionsDB")
    monkeypatch.setenv("IGS_POSITIONSDB_USER", "u")
    monkeypatch.setenv("IGS_POSITIONSDB_PASSWORD", "pw")
    url = R.make_url("positionsdb")
    q = url.query
    assert q["driver"] == "ODBC Driver 18 for SQL Server"
    assert q["Encrypt"] == "yes"
    assert q["TrustServerCertificate"] == "no"
    # No legacy server\instance backslash form.
    assert "\\" not in (url.host or "")


def test_sqlserver_driver_overridable(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_SQLSERVER_DRIVER", "ODBC Driver 17 for SQL Server")
    monkeypatch.setenv("IGS_REFDB_HOST", "w.example")
    monkeypatch.setenv("IGS_REFDB_DATABASE", "RefDB")
    url = R.make_url("refdb")
    assert url.query["driver"] == "ODBC Driver 17 for SQL Server"


# -------- URL-special-char passwords via URL.create -----------------------
def test_special_char_password_is_escaped(monkeypatch):
    _clear(monkeypatch)
    nasty = "p@ss:w/rd?#%x"
    monkeypatch.setenv("IGS_POSITIONSDB_HOST", "h")
    monkeypatch.setenv("IGS_POSITIONSDB_DATABASE", "db")
    monkeypatch.setenv("IGS_POSITIONSDB_USER", "u")
    monkeypatch.setenv("IGS_POSITIONSDB_PASSWORD", nasty)
    url = R.make_url("positionsdb")
    # The URL object keeps the raw password; render_as_string must escape it and
    # round-trip back to the exact same secret.
    from sqlalchemy.engine import make_url
    rendered = url.render_as_string(hide_password=False)
    assert R.__name__  # module loaded
    round_trip = make_url(rendered)
    assert round_trip.password == nasty
    # Special chars must not appear raw in the escaped userinfo section.
    assert "p@ss:w/rd?#%x" not in rendered


# -------- full-URL override wins ------------------------------------------
def test_full_url_override_wins(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_POSITIONSDB_HOST", "ignored.example")
    monkeypatch.setenv("IGS_POSITIONSDB_DATABASE", "ignored")
    monkeypatch.setenv(
        "IGS_POSITIONSDB_URL",
        "mssql+pyodbc://u:pw@override.example:1444/OverrideDB?driver=ODBC+Driver+18+for+SQL+Server",
    )
    url = R.make_url("positionsdb")
    assert url.host == "override.example"
    assert url.port == 1444
    assert url.database == "OverrideDB"


# -------- SignalStore PG + sslmode ---------------------------------------------
def test_signalstore_postgres_with_sslmode(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_SIGNALSTORE_HOST", "pg.example")
    monkeypatch.setenv("IGS_SIGNALSTORE_PORT", "5432")
    monkeypatch.setenv("IGS_SIGNALSTORE_DATABASE", "signalstore")
    monkeypatch.setenv("IGS_SIGNALSTORE_USER", "qu")
    monkeypatch.setenv("IGS_SIGNALSTORE_PASSWORD", "qp")
    monkeypatch.setenv("IGS_SIGNALSTORE_SSLMODE", "require")
    url = R.make_url("signalstore")
    assert url.drivername == "postgresql+psycopg2"
    assert url.query["sslmode"] == "require"
    assert url.port == 5432


# -------- ExecAPI / RiskAPI creds --------------------------------------------------
def test_riskapi_uses_own_creds_when_supplied(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_EXECAPI_BASE_URL", "https://execapi.example")
    monkeypatch.setenv("IGS_EXECAPI_USER", "execapiu")
    monkeypatch.setenv("IGS_EXECAPI_PASSWORD", "execapip")
    monkeypatch.setenv("IGS_RISKAPI_BASE_URL", "https://riskapi.example")
    monkeypatch.setenv("IGS_RISKAPI_USER", "riskapiu")
    monkeypatch.setenv("IGS_RISKAPI_PASSWORD", "riskapip")
    cfg = R.http_config("riskapi")
    assert cfg.base_url == "https://riskapi.example"
    assert cfg.username == "riskapiu"
    assert cfg.cred_source == "riskapi"


def test_riskapi_falls_back_to_execapi_when_no_riskapi_creds(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_EXECAPI_BASE_URL", "https://execapi.example")
    monkeypatch.setenv("IGS_EXECAPI_USER", "execapiu")
    monkeypatch.setenv("IGS_EXECAPI_PASSWORD", "execapip")
    monkeypatch.setenv("IGS_RISKAPI_BASE_URL", "https://riskapi.example")
    cfg = R.http_config("riskapi")
    assert cfg.username == "execapiu"
    assert cfg.cred_source == "execapi"


def test_make_url_rejects_http_source(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_EXECAPI_BASE_URL", "https://execapi.example")
    with pytest.raises(R.ResolverConfigError):
        R.make_url("execapi")


# -------- VITE_* secret refusal -------------------------------------------
def test_refuses_vite_secret(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("IGS_POSITIONSDB_HOST", "h")
    monkeypatch.setenv("IGS_POSITIONSDB_DATABASE", "db")
    monkeypatch.setenv("VITE_DB_PASSWORD", "leaked")
    with pytest.raises(R.ResolverConfigError):
        R.make_url("positionsdb")


# -------- missing config names the source, no values ----------------------
def test_missing_config_names_source_only(monkeypatch):
    _clear(monkeypatch)
    with pytest.raises(R.ResolverConfigError) as ei:
        R.make_url("warehouse")
    msg = str(ei.value)
    assert "warehouse" in msg
    assert "IGS_WAREHOUSE_HOST" in msg


# ---------------------------------------------------------------------------
# Kerberos / Integrated-auth mode (macOS route proven with kinit + Driver 18)
# ---------------------------------------------------------------------------
def _clear_igs_env():
    import os
    for k in list(os.environ):
        if k.startswith("IGS_"):
            del os.environ[k]


def test_integrated_named_instance_sends_no_creds(monkeypatch):
    """Integrated auth + named instance: no user/pass, Trusted_Connection=yes,
    server folded as HOST\\INSTANCE, no host/port on the URL."""
    from dashboard_adapter import db_resolver as R
    _clear_igs_env()
    p = R.SQLSERVER_PREFIXES["positionsdb"]
    monkeypatch.setenv(p + "HOST", "prodhost.dai.netdai.com")
    monkeypatch.setenv(p + "INSTANCE", "BACKTESTING")
    monkeypatch.setenv(p + "DATABASE", "PositionsDB")
    url = R._mssql_url("positionsdb")
    q = dict(url.query)
    assert url.username is None and url.password is None
    assert q["Trusted_Connection"] == "yes"
    assert q["server"] == "prodhost.dai.netdai.com\\BACKTESTING"
    assert url.host is None and url.port is None


def test_auth_kerberos_overrides_present_user(monkeypatch):
    from dashboard_adapter import db_resolver as R
    _clear_igs_env()
    p = R.SQLSERVER_PREFIXES["positionsdb"]
    monkeypatch.setenv(p + "HOST", "h")
    monkeypatch.setenv(p + "INSTANCE", "BACKTESTING")
    monkeypatch.setenv(p + "DATABASE", "db")
    monkeypatch.setenv(p + "USER", "someuser")
    monkeypatch.setenv("IGS_SQLSERVER_AUTH", "kerberos")
    url = R._mssql_url("positionsdb")
    assert url.username is None
    assert dict(url.query)["Trusted_Connection"] == "yes"


def test_sql_auth_unchanged(monkeypatch):
    """Default (USER present, no AUTH) stays classic SQL auth, no Trusted flag."""
    from dashboard_adapter import db_resolver as R
    _clear_igs_env()
    p = R.SQLSERVER_PREFIXES["positionsdb"]
    monkeypatch.setenv(p + "HOST", "h")
    monkeypatch.setenv(p + "PORT", "1433")
    monkeypatch.setenv(p + "DATABASE", "db")
    monkeypatch.setenv(p + "USER", "sqluser")
    monkeypatch.setenv(p + "PASSWORD", "p@ss:w/rd")
    url = R._mssql_url("positionsdb")
    q = dict(url.query)
    assert url.username == "sqluser"
    assert "Trusted_Connection" not in q
    assert url.host == "h" and url.port == 1433
    # special chars still escaped
    assert "p%40ss%3Aw%2Frd" in url.render_as_string(hide_password=False)


def test_integrated_with_explicit_port(monkeypatch):
    from dashboard_adapter import db_resolver as R
    _clear_igs_env()
    p = R.SQLSERVER_PREFIXES["positionsdb"]
    monkeypatch.setenv(p + "HOST", "h")
    monkeypatch.setenv(p + "PORT", "1433")
    monkeypatch.setenv(p + "DATABASE", "db")
    monkeypatch.setenv("IGS_SQLSERVER_AUTH", "integrated")
    url = R._mssql_url("positionsdb")
    q = dict(url.query)
    assert url.host == "h" and url.port == 1433
    assert q["Trusted_Connection"] == "yes" and "server" not in q
