"""
live_config.py — fail-closed live source configuration for IGS Daily Monitor.

Design goals (S3):
  * No live mode silently defaults to stage. Live requires IGS_ENV explicitly.
  * Live mode fails LOUDLY and CLEARLY when IGS_ENV is missing/invalid.
  * All paths are pathlib-based / absolute.
  * Production secrets come ONLY from environment variables (or a documented
    secure local provider); NEVER hardcoded, NEVER from VITE_* variables.
  * Missing source config names the source WITHOUT exposing any value.
  * artifact-only mode stays usable with NO database drivers installed.

This module never opens a connection and never prints a secret. It only resolves
and validates configuration. Connectivity is exercised separately by the
read-only doctor (live_source_doctor.py) under explicit gates.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------- constants
VALID_ENVS = ("prod", "altprod", "stage", "dev")
LIVE_ENVS = ("prod", "altprod")          # envs that touch real production data

# Env vars that carry secrets — used only to detect presence, never printed.
# Each entry: logical source name -> tuple of env var names that must be set.
REQUIRED_SOURCE_ENV: Dict[str, tuple] = {
    "PositionsDB":         ("IGS_POSITIONSDB_URL",),
    "warehouse":          ("IGS_WAREHOUSE_URL",),
    "TimeSeriesDB":     ("IGS_TIMESERIESDB_URL",),
    "RefDB":            ("IGS_REFDB_URL",),
    "SignalStore":           ("IGS_SIGNALSTORE_URL",),
    "ExecAPI":              ("IGS_EXECAPI_BASE_URL", "IGS_EXECAPI_USER", "IGS_EXECAPI_PASSWORD"),
    "RiskAPI":              ("IGS_RISKAPI_BASE_URL",),
}

# The minimal set needed for the five core dashboard sections.
CORE_SOURCES = ("PositionsDB", "warehouse", "SignalStore", "ExecAPI", "RiskAPI")
# Optional enrichment sources.
OPTIONAL_SOURCES = ("TimeSeriesDB", "RefDB")

# Any variable a browser could see MUST NOT hold a secret.
FORBIDDEN_SECRET_PREFIXES = ("VITE_",)


class LiveConfigError(RuntimeError):
    """Raised when live configuration is missing or unsafe. Message never
    contains a secret value — only variable/source *names*."""


# ------------------------------------------------------------------ helpers
def _bool_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def is_live_allowed() -> bool:
    """True only if the operator explicitly enabled live access."""
    return _bool_env("IGS_ALLOW_LIVE")


def get_env(*, require: bool = False) -> Optional[str]:
    """
    Resolve IGS_ENV. Unlike the legacy utils/config.get_env(), this NEVER
    silently returns 'stage'. When require=True (live mode) a missing or invalid
    IGS_ENV raises LiveConfigError.
    """
    env = os.environ.get("IGS_ENV", "").strip().lower()
    if not env:
        if require:
            raise LiveConfigError(
                "IGS_ENV is not set. Live mode refuses to default to 'stage'. "
                f"Set IGS_ENV to one of {VALID_ENVS} explicitly."
            )
        return None
    if env not in VALID_ENVS:
        raise LiveConfigError(
            f"IGS_ENV='{env}' is not a recognised environment "
            f"(expected one of {VALID_ENVS})."
        )
    return env


def is_live_env(env: Optional[str]) -> bool:
    return env in LIVE_ENVS


# ------------------------------------------------------------------ paths
def artifact_dir(*, create: bool = False) -> Path:
    """
    Absolute artifact output directory (pathlib). Resolved from
    IGS_DASHBOARD_CAPTURE_DIR; falls back to <cwd>/pipeline_output only for
    offline/dev. Always returned as an absolute Path.
    """
    raw = os.environ.get("IGS_DASHBOARD_CAPTURE_DIR", "").strip()
    p = Path(raw) if raw else (Path.cwd() / "pipeline_output")
    p = p.expanduser().resolve()
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def require_absolute_artifact_dir() -> Path:
    """Live/intraday runs must use an explicit absolute artifact dir."""
    raw = os.environ.get("IGS_DASHBOARD_CAPTURE_DIR", "").strip()
    if not raw:
        raise LiveConfigError(
            "IGS_DASHBOARD_CAPTURE_DIR is not set. Live/intraday runs require an "
            "explicit absolute artifact directory (no implicit cwd fallback)."
        )
    p = Path(raw).expanduser()
    if not p.is_absolute():
        raise LiveConfigError(
            "IGS_DASHBOARD_CAPTURE_DIR must be an ABSOLUTE path "
            "(pathlib .is_absolute() failed)."
        )
    return p.resolve()


# ------------------------------------------------------------------ validation
@dataclass
class ConfigStatus:
    env: Optional[str]
    live: bool
    missing_sources: List[str] = field(default_factory=list)   # names only
    forbidden_secret_vars: List[str] = field(default_factory=list)
    ok: bool = True


def _scan_forbidden_secret_vars() -> List[str]:
    """Detect any browser-visible (VITE_*) variable that looks like it holds a
    credential. Returns NAMES only — never values."""
    hits = []
    secretish = ("PASSWORD", "PWD", "SECRET", "TOKEN", "URL", "USER", "KEY")
    for name in os.environ:
        if any(name.startswith(pref) for pref in FORBIDDEN_SECRET_PREFIXES):
            if any(s in name.upper() for s in secretish):
                hits.append(name)
    return sorted(hits)


def validate(*, sources: Optional[tuple] = None,
             require_live: bool = False) -> ConfigStatus:
    """
    Validate live configuration. When require_live=True:
      * IGS_ENV must be set and valid (else LiveConfigError);
      * every required source env var must be present (missing ones are
        reported by NAME only);
      * no VITE_* variable may hold a secret.
    In non-live (artifact-only / offline) mode this is advisory and never
    requires database drivers.
    """
    env = get_env(require=require_live)
    live = is_live_env(env)
    sources = sources or CORE_SOURCES

    status = ConfigStatus(env=env, live=live)

    # forbidden browser-visible secrets — always checked
    status.forbidden_secret_vars = _scan_forbidden_secret_vars()

    if require_live:
        for src in sources:
            needed = REQUIRED_SOURCE_ENV.get(src, ())
            # report the source as missing if ANY of its vars is absent
            if any(not os.environ.get(v, "").strip() for v in needed):
                status.missing_sources.append(src)

    status.ok = (not status.missing_sources) and (not status.forbidden_secret_vars)
    if require_live and not env:
        status.ok = False
    return status


def assert_live_ready(sources: Optional[tuple] = None) -> ConfigStatus:
    """
    Hard gate for a live run. Raises LiveConfigError (naming the problem, never
    a value) unless everything required for live is present and safe.
    """
    if not is_live_allowed():
        raise LiveConfigError(
            "Live access is not enabled. Set IGS_ALLOW_LIVE=1 and pass the "
            "explicit --confirm-live flag before any live source is contacted."
        )
    status = validate(sources=sources, require_live=True)
    if status.forbidden_secret_vars:
        raise LiveConfigError(
            "Refusing to run: browser-visible variables appear to hold secrets: "
            + ", ".join(status.forbidden_secret_vars)
            + ". Secrets must never live in VITE_* variables."
        )
    if status.missing_sources:
        raise LiveConfigError(
            "Missing live source configuration for: "
            + ", ".join(status.missing_sources)
            + ". Set the corresponding IGS_* environment variables "
              "(see .env.live.example). No values are shown for safety."
        )
    return status


# --------------------------------------------------------- redacted report
def redacted_report(sources: Optional[tuple] = None,
                    require_live: bool = False) -> str:
    """
    Human-readable configuration report. Prints PRESENT/MISSING per source and
    per env var — NEVER the value. Safe to log.
    """
    sources = sources or (CORE_SOURCES + OPTIONAL_SOURCES)
    lines = ["IGS live configuration report (redacted)"]
    try:
        env = get_env(require=require_live)
        lines.append(f"  IGS_ENV            : {env or '(unset)'}")
    except LiveConfigError as e:
        lines.append(f"  IGS_ENV            : ERROR — {e}")
        env = None
    lines.append(f"  IGS_ALLOW_LIVE     : {'yes' if is_live_allowed() else 'no'}")
    lines.append(f"  live env?          : {is_live_env(env)}")

    raw_dir = os.environ.get("IGS_DASHBOARD_CAPTURE_DIR", "").strip()
    lines.append(f"  artifact dir set?  : {'yes' if raw_dir else 'no'}"
                 f"{' (absolute)' if raw_dir and Path(raw_dir).is_absolute() else ''}")

    lines.append("  sources:")
    for src in sources:
        needed = REQUIRED_SOURCE_ENV.get(src, ())
        parts = []
        for v in needed:
            present = bool(os.environ.get(v, "").strip())
            parts.append(f"{v}={'PRESENT' if present else 'MISSING'}")
        tag = "required" if src in CORE_SOURCES else "optional"
        lines.append(f"    - {src:<14} [{tag}] : " + ", ".join(parts))

    forbidden = _scan_forbidden_secret_vars()
    if forbidden:
        lines.append("  ⚠ VITE_* secret-like vars (FORBIDDEN): "
                     + ", ".join(forbidden))
    else:
        lines.append("  VITE_* secret check: clean")
    return "\n".join(lines)


if __name__ == "__main__":  # `python3 -m dashboard_adapter.live_config`
    import argparse
    ap = argparse.ArgumentParser(description="Redacted live-config report.")
    ap.add_argument("--require-live", action="store_true",
                    help="Validate as if preparing a live run (fail-closed).")
    args = ap.parse_args()
    print(redacted_report(require_live=args.require_live))
    # nonzero exit if a live check would fail (no traceback — report is enough)
    if args.require_live:
        try:
            st = validate(require_live=True)
            raise SystemExit(0 if st.ok else 3)
        except LiveConfigError:
            raise SystemExit(3)
