"""Shared runtime flags (avoid re-importing app from blueprints)."""

from __future__ import annotations

DB_READY: bool = False
DB_INIT_ERROR: str | None = None


def set_database_status(*, ready: bool, error: str | None) -> None:
    global DB_READY, DB_INIT_ERROR
    DB_READY = ready
    DB_INIT_ERROR = error
