"""Dedicated SQLite database for agent chat (separate from any main app DB)."""

from __future__ import annotations

import sqlite3

from remote_sqlite import connect_sqlite
from storage_paths import storage_dir

STORAGE_DIR = storage_dir()
CHAT_DB_PATH = STORAGE_DIR / "agent_chat.sqlite"

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS chat_threads (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'agent', 'system')),
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES chat_threads (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread
    ON chat_messages (thread_id, created_at);

CREATE TABLE IF NOT EXISTS chat_drafts (
    thread_id TEXT PRIMARY KEY,
    body TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES chat_threads (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_draft_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES chat_threads (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_draft_files_thread
    ON chat_draft_files (thread_id);

CREATE TABLE IF NOT EXISTS chat_message_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    stored_name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES chat_messages (id) ON DELETE CASCADE
);
"""


def _migrate_chat_threads(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(chat_threads)").fetchall()}
    if "workspace_id" not in columns:
        conn.execute("ALTER TABLE chat_threads ADD COLUMN workspace_id TEXT")
    if "kind" not in columns:
        conn.execute("ALTER TABLE chat_threads ADD COLUMN kind TEXT NOT NULL DEFAULT 'main'")
    if "title" not in columns:
        conn.execute("ALTER TABLE chat_threads ADD COLUMN title TEXT NOT NULL DEFAULT 'Main chat'")


def init_chat_database() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    (STORAGE_DIR / "chat_files").mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)
        _migrate_chat_threads(conn)
        conn.commit()


def connect() -> sqlite3.Connection:
    return connect_sqlite(path=CHAT_DB_PATH)
