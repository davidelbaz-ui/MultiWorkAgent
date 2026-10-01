"""Test database connections and capture read-only schema metadata."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

SUPPORTED_ENGINES = frozenset({"sqlite", "postgresql", "mysql"})
MAX_TABLES = 100


class DatabaseConnectionError(Exception):
    pass


def _sqlite_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    rows = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        LIMIT ?
        """,
        (MAX_TABLES,),
    ).fetchall()
    for row in rows:
        table_name = row[0]
        safe_name = table_name.replace('"', '""')
        columns = conn.execute(f'PRAGMA table_info("{safe_name}")').fetchall()
        tables.append(
            {
                "name": table_name,
                "columns": [
                    {"name": col[1], "type": col[2] or "unknown"} for col in columns
                ],
            }
        )
    return {"engine": "sqlite", "tables": tables, "table_count": len(tables)}


def _postgres_schema(dsn: str) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:
        raise DatabaseConnectionError(
            "PostgreSQL driver not installed (pip install psycopg[binary])."
        ) from exc

    tables: list[dict[str, Any]] = []
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                LIMIT %s
                """,
                (MAX_TABLES,),
            )
            table_names = [row[0] for row in cur.fetchall()]
            for table_name in table_names:
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table_name,),
                )
                columns = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
                tables.append({"name": table_name, "columns": columns})
    return {"engine": "postgresql", "tables": tables, "table_count": len(tables)}


def _mysql_schema(dsn: str) -> dict[str, Any]:
    try:
        import pymysql
    except ImportError as exc:
        raise DatabaseConnectionError(
            "MySQL driver not installed (pip install pymysql)."
        ) from exc

    tables: list[dict[str, Any]] = []
    conn = pymysql.connect(
        host=dsn["host"],
        port=dsn["port"],
        user=dsn["user"],
        password=dsn["password"],
        database=dsn["database"],
        connect_timeout=10,
        read_timeout=10,
        cursorclass=pymysql.cursors.Cursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
                LIMIT %s
                """,
                (dsn["database"], MAX_TABLES),
            )
            table_names = [row[0] for row in cur.fetchall()]
            for table_name in table_names:
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (dsn["database"], table_name),
                )
                columns = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
                tables.append({"name": table_name, "columns": columns})
    finally:
        conn.close()
    return {"engine": "mysql", "tables": tables, "table_count": len(tables)}


def build_connection_hint(*, engine: str, host: str, port: int | None, database_name: str, username: str) -> str:
    if engine == "sqlite":
        return f"sqlite · {database_name}"
    port_part = f":{port}" if port else ""
    user_part = username or "user"
    return f"{engine} · {user_part}@{host}{port_part}/{database_name}"


def test_and_introspect(
    *,
    engine: str,
    host: str,
    port: int | None,
    database_name: str,
    username: str,
    password: str,
) -> dict[str, Any]:
    engine = engine.strip().lower()
    if engine not in SUPPORTED_ENGINES:
        raise DatabaseConnectionError(f"Unsupported engine: {engine}")

    if engine == "sqlite":
        path = database_name.strip()
        if not path:
            raise DatabaseConnectionError("database path is required for sqlite")
        try:
            conn = sqlite3.connect(path, timeout=10)
            conn.execute("SELECT 1")
            schema = _sqlite_schema(conn)
            conn.close()
        except sqlite3.Error as exc:
            raise DatabaseConnectionError(str(exc)) from exc
        return schema

    if engine == "postgresql":
        try:
            import psycopg
        except ImportError as exc:
            raise DatabaseConnectionError(
                "PostgreSQL driver not installed (pip install psycopg[binary])."
            ) from exc
        if not host.strip():
            raise DatabaseConnectionError("host is required for postgresql")
        dsn = (
            f"host={host} port={port or 5432} dbname={database_name} "
            f"user={username} password={password}"
        )
        try:
            with psycopg.connect(dsn, connect_timeout=10) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return _postgres_schema(dsn)
        except Exception as exc:
            raise DatabaseConnectionError(str(exc)) from exc

    if engine == "mysql":
        if not host.strip():
            raise DatabaseConnectionError("host is required for mysql")
        dsn = {
            "host": host,
            "port": port or 3306,
            "user": username,
            "password": password,
            "database": database_name,
        }
        try:
            import pymysql

            conn = pymysql.connect(
                host=dsn["host"],
                port=dsn["port"],
                user=dsn["user"],
                password=dsn["password"],
                database=dsn["database"],
                connect_timeout=10,
            )
            conn.close()
            return _mysql_schema(dsn)
        except ImportError as exc:
            raise DatabaseConnectionError(
                "MySQL driver not installed (pip install pymysql)."
            ) from exc
        except Exception as exc:
            raise DatabaseConnectionError(str(exc)) from exc

    raise DatabaseConnectionError(f"Unsupported engine: {engine}")


def schema_summary(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "Schema not synced"
    count = schema.get("table_count")
    if count is None:
        count = len(schema.get("tables") or [])
    return f"{count} tables cached"


def schema_to_json(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False)
