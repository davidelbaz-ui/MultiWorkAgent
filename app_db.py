"""Primary SQLite database for accounts, businesses, and app domain data."""

from __future__ import annotations

import sqlite3

from app_migrations import APP_SCHEMA_VERSION, current_schema_version, run_migrations
from storage_paths import storage_dir

STORAGE_DIR = storage_dir()
APP_DB_PATH = STORAGE_DIR / "app.sqlite"


def init_app_database() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        run_migrations(conn)
        conn.commit()


def get_app_schema_version() -> int:
    """Latest applied migration version (0 if database file does not exist yet)."""
    if not APP_DB_PATH.is_file():
        return 0
    with connect() as conn:
        return current_schema_version(conn)


def expected_app_schema_version() -> int:
    return APP_SCHEMA_VERSION


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(APP_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
