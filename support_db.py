"""Dedicated SQLite database for contact-support conversations."""

from __future__ import annotations

import sqlite3

from remote_sqlite import connect_sqlite
from storage_paths import storage_dir

SUPPORT_DB_PATH = storage_dir() / "support.sqlite"


def connect() -> sqlite3.Connection:
    return connect_sqlite(path=SUPPORT_DB_PATH)
