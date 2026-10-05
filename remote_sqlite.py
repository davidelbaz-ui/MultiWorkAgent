"""Local SQLite files or remote Turso/libSQL (single cloud DB for all app data)."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from app_config import is_vercel_runtime

LOGGER = logging.getLogger(__name__)


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


class _RowMapping:
    """Dict-like row for libsql cursors (sqlite3.Row requires sqlite3.Cursor)."""

    __slots__ = ("_keys", "_values")

    def __init__(self, keys: list[str], values: tuple[Any, ...]) -> None:
        self._keys = keys
        self._values = values

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._keys.index(key)]

    def keys(self) -> list[str]:
        return list(self._keys)

    def __iter__(self):
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._values)


class _LibsqlCursor:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def _column_names(self) -> list[str]:
        description = getattr(self._inner, "description", None) or []
        return [str(col[0]) for col in description]

    def _map_row(self, row: Any) -> Any:
        if row is None:
            return None
        return _RowMapping(self._column_names(), tuple(row))

    def fetchone(self) -> Any:
        return self._map_row(self._inner.fetchone())

    def fetchall(self) -> list[Any]:
        return [self._map_row(row) for row in self._inner.fetchall()]

    def fetchmany(self, size: int | None = None) -> list[Any]:
        rows = self._inner.fetchmany(size) if size is not None else self._inner.fetchmany()
        return [self._map_row(row) for row in rows]

    @property
    def lastrowid(self) -> Any:
        return self._inner.lastrowid

    @property
    def rowcount(self) -> int:
        return int(self._inner.rowcount)


class _LibsqlConnection:
    """sqlite3-compatible wrapper for libsql remote connections."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.row_factory: Any = sqlite3.Row  # ignored; rows are always _RowMapping

    def execute(self, sql: str, params: Any = ()) -> _LibsqlCursor:
        if params:
            cursor = self._inner.execute(sql, params)
        else:
            cursor = self._inner.execute(sql)
        return _LibsqlCursor(cursor)

    def executemany(self, sql: str, params: Any) -> _LibsqlCursor:
        cursor = self._inner.executemany(sql, params)
        return _LibsqlCursor(cursor)

    def executescript(self, script: str) -> None:
        self._inner.executescript(script)

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> _LibsqlConnection:
        self._inner.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return self._inner.__exit__(exc_type, exc, tb)


def _connect_libsql(url: str, token: str) -> _LibsqlConnection:
    import libsql

    inner = libsql.connect(database=url, auth_token=token)
    conn = _LibsqlConnection(inner)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def connect_sqlite(*, path: Path) -> sqlite3.Connection | _LibsqlConnection:
    creds = turso_credentials()
    if creds:
        url, token = creds
        try:
            return _connect_libsql(url, token)
        except Exception as exc:
            if _env_bool("TURSO_REQUIRED"):
                raise RuntimeError(
                    "Could not connect to Turso (TURSO_REQUIRED=1). "
                    "Check TURSO_DATABASE_URL and TURSO_AUTH_TOKEN."
                ) from exc
            LOGGER.warning(
                "Turso connection failed; falling back to local SQLite at %s: %s",
                path,
                exc,
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
