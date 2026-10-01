"""Writable storage root (local `storage/` or ephemeral `/tmp` on Vercel)."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def is_vercel_runtime() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def storage_dir() -> Path:
    if is_vercel_runtime():
        path = Path("/tmp/multiworkagent/storage")
    else:
        path = APP_DIR / "storage"
    path.mkdir(parents=True, exist_ok=True)
    return path
