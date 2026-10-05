"""PostgreSQL application database (DATABASE_URL). Psycopg with sqlite-style ? placeholders."""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from app_config import is_vercel_runtime

_PLACEHOLDER_RE = re.compile(r"\?")


class DBRow(dict):
    """Row with attribute and index access like sqlite3.Row."""

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class DBCursor:
    def __init__(self, cursor: psycopg.Cursor) -> None:
        self._cursor = cursor
        self._rows: list[DBRow] | None = None
        self._index = 0

    @property
    def lastrowid(self) -> Any:
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def _materialize(self) -> list[DBRow]:
        if self._rows is None:
            raw = self._cursor.fetchall()
            self._rows = [DBRow(row) for row in raw]
        return self._rows

    def fetchone(self) -> DBRow | None:
        if self._rows is not None:
            if self._index >= len(self._rows):
                return None
            row = self._rows[self._index]
            self._index += 1
            return row
        raw = self._cursor.fetchone()
        if raw is None:
            return None
        return DBRow(raw)

    def fetchall(self) -> list[DBRow]:
        return list(self._materialize())

    def fetchmany(self, size: int | None = None) -> list[DBRow]:
        if self._rows is None:
            raw = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
            return [DBRow(row) for row in raw]
        chunk = self._rows[self._index : self._index + (size or len(self._rows))]
        self._index += len(chunk)
        return chunk


class DBConnection:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn
        self.row_factory = DBRow

    def execute(self, sql: str, params: Any = ()) -> DBCursor:
        pg_sql = _PLACEHOLDER_RE.sub("%s", sql)
        cursor = self._conn.cursor(row_factory=dict_row)
        if params:
            cursor.execute(pg_sql, params)
        else:
            cursor.execute(pg_sql)
        return DBCursor(cursor)

    def executemany(self, sql: str, params: Any) -> DBCursor:
        pg_sql = _PLACEHOLDER_RE.sub("%s", sql)
        cursor = self._conn.cursor(row_factory=dict_row)
        cursor.executemany(pg_sql, params)
        return DBCursor(cursor)

    def executescript(self, script: str) -> None:
        statements = [part.strip() for part in script.split(";") if part.strip()]
        for statement in statements:
            if statement.upper().startswith("PRAGMA"):
                continue
            self.execute(statement)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> DBConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


def _normalize_postgres_url(raw: str) -> str:
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def _url_host(url: str) -> str:
    return (urlparse(url).hostname or "").strip().lower()


def _is_local_database_host(url: str) -> bool:
    host = _url_host(url)
    return host in ("127.0.0.1", "localhost", "::1")


def _env_url_keys() -> tuple[str, ...]:
    if is_vercel_runtime():
        return (
            "POSTGRES_URL",
            "POSTGRES_PRISMA_URL",
            "POSTGRES_URL_NON_POOLING",
            "DATABASE_URL",
        )
    return (
        "DATABASE_URL",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
        "POSTGRES_URL_NON_POOLING",
    )


def database_url() -> str:
    candidates: list[str] = []
    for key in _env_url_keys():
        raw = os.environ.get(key, "").strip()
        if raw:
            candidates.append(_normalize_postgres_url(raw))
    if not candidates:
        return ""
    if is_vercel_runtime():
        for url in candidates:
            if not _is_local_database_host(url):
                return url
        return ""
    return candidates[0]


def deployment_database_error() -> str | None:
    """Explain misconfiguration before connecting (especially localhost on Vercel)."""
    if not is_vercel_runtime():
        return None
    raw_urls = [
        _normalize_postgres_url(os.environ.get(key, ""))
        for key in _env_url_keys()
        if os.environ.get(key, "").strip()
    ]
    if not raw_urls:
        return None
    remote = [u for u in raw_urls if not _is_local_database_host(u)]
    if remote:
        return None
    return (
        "DATABASE_URL points to 127.0.0.1 (localhost). That only works on your computer, not on Vercel. "
        "In Vercel: Storage → connect Postgres (uses POSTGRES_URL with a remote host), then remove any "
        "DATABASE_URL that copies your local .env, and redeploy."
    )


def require_database_url() -> str:
    url = database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required (postgresql://user:password@host:5432/dbname). "
            "On Vercel, use Vercel Postgres or Neon and set DATABASE_URL in Environment Variables."
        )
    return url


def connect() -> DBConnection:
    return DBConnection(
        psycopg.connect(require_database_url(), autocommit=False, connect_timeout=15)
    )


def table_exists(conn: DBConnection, name: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ?
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    return row is not None


def column_names(conn: DBConnection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = ?
        """,
        (table,),
    ).fetchall()
    return {str(row["column_name"]) for row in rows}
