"""Agent chat persistence (PostgreSQL, shared DATABASE_URL)."""

from __future__ import annotations

from db_connection import DBConnection, connect
from storage_paths import storage_dir

STORAGE_DIR = storage_dir()


def init_chat_database() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    (STORAGE_DIR / "chat_files").mkdir(parents=True, exist_ok=True)


__all__ = ["STORAGE_DIR", "connect", "init_chat_database", "DBConnection"]
