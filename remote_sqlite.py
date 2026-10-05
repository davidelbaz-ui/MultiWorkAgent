"""Local SQLite files or remote Turso/libSQL (single cloud DB for all app data)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from app_config import is_vercel_runtime


def turso_credentials() -> tuple[str, str] | None:
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if url and token:
        return url, token
    return None


def uses_remote_database() -> bool:
    return turso_credentials() is not None


def ephemeral_local_storage() -> bool:
    if uses_remote_database():
        return False
    if is_vercel_runtime():
        return True
    return _env_bool("EPHEMERAL_STORAGE")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def should_trust_session_membership() -> bool:
    """When local DB is ephemeral, rely on signed session after login."""
    if _env_bool("AUTH_TRUST_SESSION_MEMBERSHIP"):
        return True
    if _env_bool("AUTH_STRICT_MEMBERSHIP"):
        return False
    return ephemeral_local_storage()


def connect_sqlite(*, path: Path) -> sqlite3.Connection:
    creds = turso_credentials()
    if creds:
        url, token = creds
        import libsql

        conn: Any = libsql.connect(database=url, auth_token=token)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
