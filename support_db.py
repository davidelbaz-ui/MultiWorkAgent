"""Dedicated SQLite database for contact-support conversations."""

from __future__ import annotations

import sqlite3

from storage_paths import storage_dir

SUPPORT_DB_PATH = storage_dir() / "support.sqlite"


def connect() -> sqlite3.Connection:
    SUPPORT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SUPPORT_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
