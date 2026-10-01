"""Per-business database connections (encrypted credentials + schema cache)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

import business_store
import database_introspect
import integration_secrets
from app_db import connect, init_app_database


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _parse_schema(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _row_to_connection(row: Any) -> dict[str, Any]:
    schema = _parse_schema(row["schema_json"])
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "business_id": row["business_id"],
        "name": row["name"],
        "engine": row["engine"],
        "host": row["host"] or "",
        "port": row["port"],
        "database_name": row["database_name"],
        "username": row["username"] or "",
        "access_mode": row["access_mode"],
        "status": row["status"],
        "connection_hint": row["connection_hint"] or "",
        "schema": schema,
        "schema_synced_at": row["schema_synced_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_connections(
    account_id: str,
    *,
    business_id: str | None = None,
) -> list[dict[str, Any]]:
    where = "account_id = ?"
    params: list[Any] = [account_id]
    if business_id:
        where += " AND business_id = ?"
        params.append(business_id)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                id, account_id, business_id, name, engine, host, port, database_name,
                username, access_mode, status, connection_hint, schema_json,
                schema_synced_at, created_at, updated_at
            FROM database_connections
            WHERE {where}
            ORDER BY updated_at DESC
            """,
            params,
        ).fetchall()
    return [_row_to_connection(row) for row in rows]


def get_connection(account_id: str, connection_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                id, account_id, business_id, name, engine, host, port, database_name,
                username, access_mode, status, secret_ciphertext, connection_hint,
                schema_json, schema_synced_at, created_at, updated_at
            FROM database_connections
            WHERE account_id = ? AND id = ?
            """,
            (account_id, connection_id),
        ).fetchone()
    if not row:
        return None
    item = _row_to_connection(row)
    return item


def get_connection_credentials(account_id: str, connection_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT secret_ciphertext, status
            FROM database_connections
            WHERE account_id = ? AND id = ?
            """,
            (account_id, connection_id),
        ).fetchone()
    if not row or row["status"] != "connected" or not row["secret_ciphertext"]:
        return None
    try:
        return integration_secrets.decrypt_credentials(row["secret_ciphertext"])
    except ValueError:
        return None


def create_connection(
    account_id: str,
    business_id: str,
    *,
    name: str,
    engine: str,
    host: str = "",
    port: int | None = None,
    database_name: str,
    username: str = "",
    password: str = "",
    access_mode: str = "read",
) -> dict[str, Any]:
    if not business_store.get_business(account_id, business_id):
        raise LookupError("business not found")

    clean_name = name.strip()
    if not clean_name:
        raise ValueError("name is required")
    clean_engine = engine.strip().lower()
    if clean_engine not in database_introspect.SUPPORTED_ENGINES:
        raise ValueError("engine must be sqlite, postgresql, or mysql")
    if access_mode not in ("read", "read_write"):
        raise ValueError("access_mode must be read or read_write")

    schema = database_introspect.test_and_introspect(
        engine=clean_engine,
        host=host,
        port=port,
        database_name=database_name,
        username=username,
        password=password,
    )

    now = _utc_now()
    connection_id = str(uuid.uuid4())
    ciphertext = integration_secrets.encrypt_credentials({"password": password})
    hint = database_introspect.build_connection_hint(
        engine=clean_engine,
        host=host,
        port=port,
        database_name=database_name,
        username=username,
    )

    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO database_connections (
                    id, account_id, business_id, name, engine, host, port, database_name,
                    username, access_mode, status, secret_ciphertext, connection_hint,
                    schema_json, schema_synced_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'connected', ?, ?, ?, ?, ?, ?)
                """,
                (
                    connection_id,
                    account_id,
                    business_id,
                    clean_name,
                    clean_engine,
                    host.strip(),
                    port,
                    database_name.strip(),
                    username.strip(),
                    access_mode,
                    ciphertext,
                    hint,
                    database_introspect.schema_to_json(schema),
                    now,
                    now,
                    now,
                ),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            "a connection with this name already exists for this business"
        ) from exc

    row = get_connection(account_id, connection_id)
    if not row:
        raise RuntimeError("failed to create database connection")
    return row


def sync_schema(account_id: str, business_id: str, connection_id: str) -> dict[str, Any]:
    creds = get_connection_credentials(account_id, connection_id)
    conn = get_connection(account_id, connection_id)
    if not conn or conn["business_id"] != business_id or not creds:
        raise LookupError("not found")

    password = creds.get("password") or ""
    schema = database_introspect.test_and_introspect(
        engine=conn["engine"],
        host=conn["host"],
        port=conn["port"],
        database_name=conn["database_name"],
        username=conn["username"],
        password=password,
    )
    now = _utc_now()
    with connect() as db:
        db.execute(
            """
            UPDATE database_connections
            SET schema_json = ?, schema_synced_at = ?, updated_at = ?, status = 'connected'
            WHERE account_id = ? AND id = ? AND business_id = ?
            """,
            (
                database_introspect.schema_to_json(schema),
                now,
                now,
                account_id,
                connection_id,
                business_id,
            ),
        )
        db.commit()
    updated = get_connection(account_id, connection_id)
    if not updated:
        raise RuntimeError("failed to update schema")
    return updated


def delete_connection(account_id: str, business_id: str, connection_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """
            DELETE FROM database_connections
            WHERE account_id = ? AND business_id = ? AND id = ?
            """,
            (account_id, business_id, connection_id),
        )
        conn.commit()
        return cur.rowcount > 0


def connection_to_api(row: dict[str, Any]) -> dict[str, Any]:
    schema = row.get("schema")
    return {
        "id": row["id"],
        "business_id": row["business_id"],
        "name": row["name"],
        "engine": row["engine"],
        "host": row["host"],
        "port": row["port"],
        "database_name": row["database_name"],
        "username": row["username"],
        "access_mode": row["access_mode"],
        "status": row["status"],
        "connection_hint": row["connection_hint"],
        "schema_summary": database_introspect.schema_summary(schema),
        "schema_synced_at": row.get("schema_synced_at"),
        "table_count": (schema or {}).get("table_count"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
