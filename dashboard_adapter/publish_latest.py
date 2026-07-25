"""
publish_latest.py — secure publication of latest.json (S7).

The React app polls latest.json every ~15s, but the pipeline only produces a new
snapshot every ~30min. This module publishes the finalized latest.json so the
poller always sees a consistent, cacheable file, in one of two modes:

  * local  : write to a Mac filesystem path the local dev/preview server serves.
  * hosted : upload to a PROTECTED internal endpoint (auth from env, never VITE_).

Safety:
  * NEVER publishes if the payload is not a finalized, non-failed snapshot.
  * NEVER publishes raw production holdings / P&L to a PUBLIC location; hosted
    mode refuses unless IGS_PUBLISH_ALLOW_SENSITIVE=1 AND the endpoint is marked
    internal (IGS_PUBLISH_ENDPOINT_INTERNAL=1).
  * Atomic writes (temp file + os.replace) so the poller never sees a partial file.
  * Emits cache-control guidance sized to the poll interval.
  * Rollback: keeps the previous good file as latest.json.bak and can restore it.
  * Auth token read from IGS_PUBLISH_AUTH_TOKEN (env only) — never a VITE_ var,
    never logged.

Do NOT upload real data in preparation; this module is invoked only during an
approved run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


class PublishError(RuntimeError):
    """Never contains a secret; names the problem only."""


CACHE_CONTROL = "no-cache, max-age=15, must-revalidate"  # matches 15s poll


def _load_payload(path: Path) -> dict:
    if not path.is_file():
        raise PublishError(f"latest.json not found at the finalized path: {path.name}")
    try:
        return json.loads(path.read_text())
    except Exception:
        raise PublishError("latest.json is not valid JSON; refusing to publish.")


def _assert_publishable(payload: dict) -> None:
    status = str(payload.get("pipelineStatus", "")).lower()
    if status == "failed":
        raise PublishError("pipelineStatus=failed; refusing to publish "
                           "(last-known-good preserved).")
    if "businessDate" not in payload or "runId" not in payload:
        raise PublishError("payload missing businessDate/runId; not a finalized "
                           "snapshot.")


def _atomic_write(dst: Path, data: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dst.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, dst)   # atomic on POSIX
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _backup(dst: Path) -> None:
    if dst.is_file():
        shutil.copy2(dst, dst.with_suffix(dst.suffix + ".bak"))


def publish_local(src: Path, dst: Path) -> dict:
    payload = _load_payload(src)
    _assert_publishable(payload)
    _backup(dst)
    _atomic_write(dst, json.dumps(payload, separators=(",", ":")).encode())
    return {"mode": "local", "dst": str(dst),
            "businessDate": payload.get("businessDate"),
            "runId": payload.get("runId"),
            "cacheControl": CACHE_CONTROL, "rollback": str(dst.with_suffix(dst.suffix + ".bak"))}


def publish_hosted(src: Path) -> dict:
    endpoint = os.environ.get("IGS_PUBLISH_ENDPOINT", "").strip()
    token = os.environ.get("IGS_PUBLISH_AUTH_TOKEN", "").strip()
    internal = os.environ.get("IGS_PUBLISH_ENDPOINT_INTERNAL", "").strip() in ("1", "true", "yes")
    allow_sensitive = os.environ.get("IGS_PUBLISH_ALLOW_SENSITIVE", "").strip() in ("1", "true", "yes")

    if not endpoint:
        raise PublishError("IGS_PUBLISH_ENDPOINT not set for hosted mode.")
    if any(k.startswith("VITE_") for k in os.environ
           if "PUBLISH" in k.upper() and ("TOKEN" in k.upper() or "AUTH" in k.upper())):
        raise PublishError("publication auth must NOT live in a VITE_* variable.")
    if not token:
        raise PublishError("IGS_PUBLISH_AUTH_TOKEN not set (env only).")
    if not internal:
        raise PublishError("hosted endpoint is not marked internal "
                           "(IGS_PUBLISH_ENDPOINT_INTERNAL=1). Refusing to publish "
                           "holdings/P&L to a non-internal target.")
    if not allow_sensitive:
        raise PublishError("IGS_PUBLISH_ALLOW_SENSITIVE=1 required to confirm the "
                           "internal endpoint may receive holdings/P&L.")

    payload = _load_payload(src)
    _assert_publishable(payload)

    try:
        import requests
    except Exception:
        raise PublishError("requests not installed; cannot use hosted mode.")

    data = json.dumps(payload, separators=(",", ":")).encode()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Cache-Control": CACHE_CONTROL,
    }
    try:
        r = requests.put(endpoint, data=data, headers=headers, timeout=15)
    except Exception:
        raise PublishError("upload failed (network/endpoint). No public data exposed.")
    if r.status_code >= 400:
        raise PublishError(f"upload rejected (HTTP {r.status_code}).")
    # never log endpoint/token
    return {"mode": "hosted", "status": r.status_code,
            "businessDate": payload.get("businessDate"),
            "runId": payload.get("runId"), "cacheControl": CACHE_CONTROL}


def rollback_local(dst: Path) -> dict:
    bak = dst.with_suffix(dst.suffix + ".bak")
    if not bak.is_file():
        raise PublishError("no backup (.bak) to roll back to.")
    _atomic_write(dst, bak.read_bytes())
    return {"mode": "rollback", "restored": str(dst)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Publish finalized latest.json (S7).")
    ap.add_argument("--mode", choices=["local", "hosted"],
                    default=os.environ.get("IGS_PUBLISH_MODE", "local"))
    ap.add_argument("--src", default=os.environ.get(
        "IGS_LATEST_PATH", "dashboard_adapter/sample_output/latest.json"))
    ap.add_argument("--dst", default=os.environ.get("IGS_PUBLISH_LOCAL_DST", ""))
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.src).expanduser()
    try:
        if args.rollback:
            dst = Path(args.dst or args.src).expanduser()
            print("[publish]", rollback_local(dst)); return 0
        if args.mode == "local":
            dst = Path(args.dst).expanduser() if args.dst else src
            print("[publish]", publish_local(src, dst)); return 0
        print("[publish]", publish_hosted(src)); return 0
    except PublishError as e:
        sys.stderr.write(f"[publish] REFUSED: {e}\n"); return 2


if __name__ == "__main__":
    raise SystemExit(main())
