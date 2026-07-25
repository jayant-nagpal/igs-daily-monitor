"""
db_resolver.py — shared, fail-closed SQLAlchemy connection resolver (S9 / item 2).

This is the SINGLE source of truth for how the IGS Daily Monitor builds database
connection URLs and HTTP endpoints. Both the producer pipeline AND the read-only
source doctor call this module, so a doctor PASS proves the *exact* configuration
the producer will use.

Design rules (non-negotiable):
  * URLs are built with ``sqlalchemy.engine.URL.create()`` — NEVER string
    interpolation — so passwords containing URL-special characters
    (``@ : / ? # %``) are escaped correctly.
  * Every source supports split env vars (``*_HOST/_PORT/_DATABASE/_USER/
    _PASSWORD``) AND an optional full-URL override (``*_URL``). The override
    wins when set.
  * SQL Server always uses ODBC Driver 18 (configurable) with
    ``Encrypt=yes`` + ``TrustServerCertificate=no`` by default, and an explicit
    FQDN + TCP port — never the legacy ``server\\instance`` backslash form.
  * A deterministic legacy alias map lets old producer code keep using its
    human aliases (``BackTesting``, ``warehouse_server`` …) while resolving to the
    new env-driven config.
  * Secrets are NEVER read from ``VITE_*`` variables and connection strings /
    passwords are NEVER logged or returned in error messages — only NAMES.
  * ``sqlalchemy`` is imported lazily so this module can be imported for its
    constants/logic even when the DB drivers (pyodbc/psycopg2) are absent.
    Actually opening a connection (``resolve_engine(...).connect()``) is what
    needs the driver.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
DEFAULT_SQLSERVER_DRIVER = "ODBC Driver 18 for SQL Server"
DEFAULT_ENCRYPT = "yes"
DEFAULT_TRUST_SERVER_CERTIFICATE = "no"

FORBIDDEN_SECRET_PREFIXES = ("VITE_",)

# Canonical source name -> kind of connection.
KIND_MSSQL = "mssql"
KIND_POSTGRES = "postgres"
KIND_HTTP = "http"

# Canonical SQL Server sources and their env-var prefix (prefix ends with "_").
SQLSERVER_PREFIXES: Dict[str, str] = {
    "positionsdb": "IGS_POSITIONSDB_",
    "positionsdb_dev": "IGS_POSITIONSDB_DEV_",
    "positionsdb_stg": "IGS_POSITIONSDB_STG_",
    "warehouse": "IGS_WAREHOUSE_",
    "timeseriesdb": "IGS_TIMESERIESDB_",
    "backtesting": "IGS_BACKTESTING_",
    "refdb": "IGS_REFDB_",
}

SIGNALSTORE_PREFIX = "IGS_SIGNALSTORE_"

# Canonical name -> kind.
SOURCE_KINDS: Dict[str, str] = {name: KIND_MSSQL for name in SQLSERVER_PREFIXES}
SOURCE_KINDS["signalstore"] = KIND_POSTGRES
SOURCE_KINDS["execapi"] = KIND_HTTP
SOURCE_KINDS["riskapi"] = KIND_HTTP

# Deterministic legacy alias -> canonical source name. Case-insensitive lookup
# (see normalize_alias). This lets legacy producer code keep its human aliases
# (e.g. the "BackTesting" ODBC DSN, "warehouse_server") while resolving to the new
# split-env configuration.
LEGACY_ALIAS_MAP: Dict[str, str] = {
    "positionsdb": "positionsdb",
    "positionsdb_dev": "positionsdb_dev",
    "positionsdb_stg": "positionsdb_stg",
    "warehouse_server": "warehouse",
    "warehouse": "warehouse",
    "timeseriesdb": "timeseriesdb",
    "backtesting": "backtesting",
    "refdb": "refdb",
    "signalstore": "signalstore",
    "execapi": "execapi",
    "riskapi": "riskapi",
}


class ResolverConfigError(RuntimeError):
    """Raised when a source's configuration is missing or unsafe.

    The message names the source / env var but NEVER contains a value.
    """


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def normalize_alias(alias: str) -> str:
    """Map a legacy/human alias to its canonical source name (case-insensitive).

    Raises ResolverConfigError for an unknown alias (naming it, no values).
    """
    if not alias:
        raise ResolverConfigError("empty source alias")
    key = str(alias).strip().lower()
    if key in LEGACY_ALIAS_MAP:
        return LEGACY_ALIAS_MAP[key]
    if key in SOURCE_KINDS:
        return key
    raise ResolverConfigError(
        f"unknown source alias {alias!r}; "
        f"known aliases: {sorted(LEGACY_ALIAS_MAP)}"
    )


def source_kind(alias: str) -> str:
    return SOURCE_KINDS[normalize_alias(alias)]


def _scan_forbidden_secret_vars() -> list:
    """Return NAMES of any VITE_* variable that looks like it holds a secret."""
    hits = []
    secretish = ("PASSWORD", "PWD", "SECRET", "TOKEN", "URL", "USER", "KEY")
    for name in os.environ:
        if any(name.startswith(p) for p in FORBIDDEN_SECRET_PREFIXES):
            if any(s in name.upper() for s in secretish):
                hits.append(name)
    return sorted(hits)


def assert_no_vite_secrets() -> None:
    hits = _scan_forbidden_secret_vars()
    if hits:
        raise ResolverConfigError(
            "browser-visible VITE_* variables appear to hold secrets: "
            + ", ".join(hits)
            + " — secrets must never live in VITE_* variables."
        )


# --------------------------------------------------------------------------
# SQL Server shared query dict
# --------------------------------------------------------------------------
def sqlserver_auth_mode(prefix: str = "") -> str:
    """Return the SQL Server auth mode: 'sql' or 'integrated' (Kerberos/Trusted).

    Precedence: a per-source ``<prefix>AUTH`` wins, else the shared
    ``IGS_SQLSERVER_AUTH``. When neither is set we INFER: if a USER is present
    for the source we assume 'sql', otherwise 'integrated' (so a Kerberos
    ``kinit`` ticket is used with no username/password). Values are
    case-insensitive; 'kerberos'/'trusted'/'windows'/'ad' all map to
    'integrated'.
    """
    raw = (_env(prefix + "AUTH") or _env("IGS_SQLSERVER_AUTH") or "").strip().lower()
    if raw in ("integrated", "kerberos", "trusted", "windows", "ad", "activedirectoryintegrated"):
        return "integrated"
    if raw in ("sql", "sqlpassword", "password"):
        return "sql"
    # inferred
    if prefix and _env(prefix + "USER"):
        return "sql"
    return "integrated"


def sqlserver_query(*, integrated: bool = False) -> Dict[str, str]:
    """The shared ODBC query parameters for every SQL Server URL.

    When ``integrated`` is True we add ``Trusted_Connection=yes`` so ODBC
    Driver 18 uses the current Kerberos ticket (the route proven to work on
    macOS with ``kinit``). No username/password is sent in that mode.
    """
    q = {
        "driver": _env("IGS_SQLSERVER_DRIVER") or DEFAULT_SQLSERVER_DRIVER,
        "Encrypt": _env("IGS_SQLSERVER_ENCRYPT") or DEFAULT_ENCRYPT,
        "TrustServerCertificate": (
            _env("IGS_SQLSERVER_TRUST_SERVER_CERTIFICATE")
            or DEFAULT_TRUST_SERVER_CERTIFICATE
        ),
    }
    if integrated:
        q["Trusted_Connection"] = "yes"
    return q


# --------------------------------------------------------------------------
# URL construction
# --------------------------------------------------------------------------
def _make_url_obj(drivername: str, *, username=None, password=None,
                  host=None, port=None, database=None, query=None):
    """Build a sqlalchemy URL via URL.create (safe special-char escaping)."""
    from sqlalchemy.engine import URL  # lazy import

    return URL.create(
        drivername,
        username=username or None,
        password=password or None,
        host=host or None,
        port=int(port) if port else None,
        database=database or None,
        query=query or {},
    )


def _override_url(prefix: str):
    """Return a sqlalchemy URL from ``<prefix>URL`` if that env var is set."""
    raw = _env(prefix + "URL")
    if not raw:
        return None
    from sqlalchemy.engine import make_url  # lazy import

    return make_url(raw)


def _mssql_url(canonical: str):
    prefix = SQLSERVER_PREFIXES[canonical]
    override = _override_url(prefix)
    if override is not None:
        return override

    host = _env(prefix + "HOST")
    database = _env(prefix + "DATABASE")
    if not host or not database:
        missing = [
            prefix + part
            for part in ("HOST", "DATABASE")
            if not _env(prefix + part)
        ]
        raise ResolverConfigError(
            f"SQL Server source '{canonical}' is not configured; "
            f"missing: {', '.join(missing)} "
            f"(or set the full-URL override {prefix}URL)."
        )

    integrated = sqlserver_auth_mode(prefix) == "integrated"
    query = sqlserver_query(integrated=integrated)

    # Named-instance support: if <prefix>INSTANCE is set and no explicit PORT,
    # fold the instance into the SERVER as HOST\INSTANCE and let SQL Browser
    # resolve the dynamic port. This is the form proven to work on the Mac.
    # (SQLAlchemy's URL host cannot contain a backslash, so instance goes in
    # the ODBC query as an explicit 'server' key, which pyodbc honors.)
    instance = _env(prefix + "INSTANCE")
    port = _env(prefix + "PORT")

    if instance and not port:
        # Put the full server\instance into the ODBC connect string via the
        # 'server' query key; leave host/port off the URL so pyodbc uses it.
        query = dict(query)
        query["server"] = f"{host}\\{instance}"
        url_host = None
        url_port = None
    else:
        url_host = host
        url_port = port

    return _make_url_obj(
        "mssql+pyodbc",
        username=None if integrated else _env(prefix + "USER"),
        password=None if integrated else _env(prefix + "PASSWORD"),
        host=url_host,
        port=url_port,
        database=database,
        query=query,
    )


def _signalstore_url():
    override = _override_url(SIGNALSTORE_PREFIX)
    if override is not None:
        return override
    host = _env(SIGNALSTORE_PREFIX + "HOST")
    database = _env(SIGNALSTORE_PREFIX + "DATABASE")
    if not host or not database:
        missing = [
            SIGNALSTORE_PREFIX + part
            for part in ("HOST", "DATABASE")
            if not _env(SIGNALSTORE_PREFIX + part)
        ]
        raise ResolverConfigError(
            "PostgreSQL source 'signalstore' is not configured; "
            f"missing: {', '.join(missing)} "
            f"(or set the full-URL override {SIGNALSTORE_PREFIX}URL)."
        )
    query = {}
    sslmode = _env(SIGNALSTORE_PREFIX + "SSLMODE")
    if sslmode:
        query["sslmode"] = sslmode
    return _make_url_obj(
        "postgresql+psycopg2",
        username=_env(SIGNALSTORE_PREFIX + "USER"),
        password=_env(SIGNALSTORE_PREFIX + "PASSWORD"),
        host=host,
        port=_env(SIGNALSTORE_PREFIX + "PORT"),
        database=database,
        query=query,
    )


def make_url(alias: str):
    """Return a sqlalchemy URL object for a DB source (alias or canonical name).

    Raises ResolverConfigError for HTTP sources (use ``http_config``) or when
    the source is not configured. Never returns/logs secret values.
    """
    assert_no_vite_secrets()
    canonical = normalize_alias(alias)
    kind = SOURCE_KINDS[canonical]
    if kind == KIND_MSSQL:
        return _mssql_url(canonical)
    if kind == KIND_POSTGRES:
        return _signalstore_url()
    raise ResolverConfigError(
        f"source '{canonical}' is an HTTP source; use http_config(alias) instead."
    )


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
def resolve_engine(alias: str, *, timeout: int = 5, **create_kwargs):
    """Build (but do NOT connect) a SQLAlchemy engine for a DB source.

    A short connect timeout is applied via connect_args by default. Opening a
    connection is what requires the underlying driver (pyodbc / psycopg2).
    """
    from sqlalchemy import create_engine  # lazy import

    canonical = normalize_alias(alias)
    url = make_url(canonical)
    kind = SOURCE_KINDS[canonical]
    connect_args = dict(create_kwargs.pop("connect_args", {}))
    if timeout is not None:
        if kind == KIND_MSSQL:
            connect_args.setdefault("timeout", timeout)
        elif kind == KIND_POSTGRES:
            connect_args.setdefault("connect_timeout", timeout)
    engine = create_engine(url, connect_args=connect_args, **create_kwargs)

    # ---- Command (statement) timeout --------------------------------------
    # pyodbc's connect_args["timeout"] above is the LOGIN timeout only. Heavy
    # slippage joins can exceed the driver's default command timeout and fail
    # mid-execution with 08S01 / 0x274C (10060) on SQLExecDirectW. pyodbc
    # exposes a per-connection command timeout via Connection.timeout (seconds;
    # 0 = wait indefinitely). Apply it on every new MSSQL connection so long
    # read-only queries get room to finish. Configurable via
    # IGS_SQL_COMMAND_TIMEOUT (default 300s).
    if kind == KIND_MSSQL:
        try:
            _cmd_to = int(os.environ.get("IGS_SQL_COMMAND_TIMEOUT", "300"))
        except ValueError:
            _cmd_to = 300
        if _cmd_to >= 0:
            from sqlalchemy import event  # lazy import

            @event.listens_for(engine, "connect")
            def _set_command_timeout(dbapi_conn, _rec):  # noqa: ANN001
                try:
                    dbapi_conn.timeout = _cmd_to
                except Exception:
                    # Non-pyodbc DBAPI or driver without .timeout: ignore.
                    pass

    return engine


# --------------------------------------------------------------------------
# HTTP sources (ExecAPI / RiskAPI)
# --------------------------------------------------------------------------
@dataclass
class HttpConfig:
    base_url: str
    username: str
    password: str
    # Which source's creds were actually used ("riskapi" or, for a RiskAPI fallback,
    # "execapi"). Never contains the values themselves.
    cred_source: str


def http_config(alias: str) -> HttpConfig:
    """Resolve base URL + basic-auth creds for an HTTP source (ExecAPI / RiskAPI).

    RiskAPI uses its OWN creds when supplied; it falls back to ExecAPI creds only when
    neither IGS_RISKAPI_USER nor IGS_RISKAPI_PASSWORD is set.
    """
    assert_no_vite_secrets()
    canonical = normalize_alias(alias)
    if SOURCE_KINDS.get(canonical) != KIND_HTTP:
        raise ResolverConfigError(f"source '{canonical}' is not an HTTP source.")

    if canonical == "execapi":
        base = _env("IGS_EXECAPI_BASE_URL")
        if not base:
            raise ResolverConfigError("HTTP source 'execapi' missing IGS_EXECAPI_BASE_URL.")
        return HttpConfig(base, _env("IGS_EXECAPI_USER"), _env("IGS_EXECAPI_PASSWORD"), "execapi")

    # RiskAPI
    base = _env("IGS_RISKAPI_BASE_URL")
    if not base:
        raise ResolverConfigError("HTTP source 'riskapi' missing IGS_RISKAPI_BASE_URL.")
    riskapi_user = _env("IGS_RISKAPI_USER")
    riskapi_pwd = _env("IGS_RISKAPI_PASSWORD")
    if riskapi_user or riskapi_pwd:
        return HttpConfig(base, riskapi_user, riskapi_pwd, "riskapi")
    # Fall back to ExecAPI creds ONLY when RiskAPI supplies none of its own.
    return HttpConfig(base, _env("IGS_EXECAPI_USER"), _env("IGS_EXECAPI_PASSWORD"), "execapi")


# --------------------------------------------------------------------------
# Redacted reporting (safe to log)
# --------------------------------------------------------------------------
def is_configured(alias: str) -> bool:
    """True if the source can build a URL/HTTP config, else False. No values."""
    try:
        canonical = normalize_alias(alias)
        if SOURCE_KINDS[canonical] == KIND_HTTP:
            http_config(canonical)
        else:
            make_url(canonical)
        return True
    except ResolverConfigError:
        return False


def redacted_report() -> str:
    """PRESENT/MISSING per source — never a value. Safe to print."""
    lines = ["IGS db_resolver configuration (redacted)"]
    q = sqlserver_query()
    lines.append(f"  SQL Server driver : {q['driver']}")
    lines.append(f"  Encrypt           : {q['Encrypt']}")
    lines.append(f"  TrustServerCert   : {q['TrustServerCertificate']}")
    for name in list(SQLSERVER_PREFIXES) + ["signalstore", "execapi", "riskapi"]:
        lines.append(f"  {name:<14}: {'CONFIGURED' if is_configured(name) else 'MISSING'}")
    forbidden = _scan_forbidden_secret_vars()
    lines.append("  VITE_* secret check: "
                 + ("clean" if not forbidden else "FORBIDDEN: " + ", ".join(forbidden)))
    return "\n".join(lines)


if __name__ == "__main__":  # python3 -m dashboard_adapter.db_resolver
    print(redacted_report())
