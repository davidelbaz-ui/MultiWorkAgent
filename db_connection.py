"""PostgreSQL application database (DATABASE_URL). Psycopg with sqlite-style ? placeholders."""

from __future__ import annotations

import os
import re
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

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


def database_url() -> str:
    raw = (
        os.environ.get("DATABASE_URL", "").strip()
        or os.environ.get("POSTGRES_URL", "").strip()
        or os.environ.get("POSTGRES_PRISMA_URL", "").strip()
    )
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    return raw


def require_database_url() -> str:
    url = database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required (postgresql://user:password@host:5432/dbname). "
            "On Vercel, use Vercel Postgres or Neon and set DATABASE_URL in Environment Variables."
        )
    return url


def connect() -> DBConnection:
    return DBConnection(psycopg.connect(require_database_url(), autocommit=False))


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
