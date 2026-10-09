"""Per-business integration connections (encrypted credentials)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import business_store
import integration_secrets
from app_db import connect, init_app_database
from integrations_catalog import get_integration


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _row_to_connection(row: Any, *, include_secret: bool = False) -> dict[str, Any]:
    item = {
        "id": row["id"],
        "account_id": row["account_id"],
        "business_id": row["business_id"],
        "provider_slug": row["provider_slug"],
        "provider_name": row["provider_name"],
        "auth_type": row["auth_type"],
        "status": row["status"],
        "credential_hint": row["credential_hint"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_secret and row["secret_ciphertext"]:
        try:
            item["credentials"] = integration_secrets.decrypt_credentials(row["secret_ciphertext"])
        except ValueError:
            item["credentials"] = None
            item["status"] = "error"
    return item


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
                id, account_id, business_id, provider_slug, provider_name,
                auth_type, status, secret_ciphertext, credential_hint,
                created_at, updated_at
            FROM integration_connections
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
                id, account_id, business_id, provider_slug, provider_name,
                auth_type, status, secret_ciphertext, credential_hint,
                created_at, updated_at
            FROM integration_connections
            WHERE account_id = ? AND id = ?
            """,
            (account_id, connection_id),
        ).fetchone()
    return _row_to_connection(row) if row else None


def get_connection_with_credentials(
    account_id: str,
    business_id: str,
    connection_id: str,
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                id, account_id, business_id, provider_slug, provider_name,
                auth_type, status, secret_ciphertext, credential_hint,
                created_at, updated_at
            FROM integration_connections
            WHERE account_id = ? AND business_id = ? AND id = ?
            """,
            (account_id, business_id, connection_id),
        ).fetchone()
    return _row_to_connection(row, include_secret=True) if row else None


def get_connection_for_business_provider(
    account_id: str,
    business_id: str,
    provider_slug: str,
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                id, account_id, business_id, provider_slug, provider_name,
                auth_type, status, secret_ciphertext, credential_hint,
                created_at, updated_at
            FROM integration_connections
            WHERE account_id = ? AND business_id = ? AND provider_slug = ?
            """,
            (account_id, business_id, provider_slug),
        ).fetchone()
    return _row_to_connection(row) if row else None


def get_connection_credentials(
    account_id: str,
    business_id: str,
    provider_slug: str,
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT secret_ciphertext, status
            FROM integration_connections
            WHERE account_id = ? AND business_id = ? AND provider_slug = ?
            """,
            (account_id, business_id, provider_slug),
        ).fetchone()
    if not row or row["status"] != "connected" or not row["secret_ciphertext"]:
        return None
    try:
        return integration_secrets.decrypt_credentials(row["secret_ciphertext"])
    except ValueError:
        return None


def connect_api_key(
    account_id: str,
    business_id: str,
    *,
    provider_slug: str,
    api_key: str,
    api_base_url: str | None = None,
    site_url: str | None = None,
) -> dict[str, Any]:
    if not business_store.get_business(account_id, business_id):
        raise LookupError("business not found")
    integration = get_integration(provider_slug)
    if not integration:
        raise ValueError("unknown provider")

    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("api_key is required")

    creds: dict[str, Any] = {"api_key": clean_key}
    for key, value in (("api_base_url", api_base_url), ("site_url", site_url)):
        if isinstance(value, str) and value.strip():
            creds[key] = value.strip()
    now = _utc_now()
    ciphertext = integration_secrets.encrypt_credentials(creds)
    hint = integration_secrets.credential_hint(clean_key)
    connection_id = str(uuid.uuid4())

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM integration_connections
            WHERE business_id = ? AND provider_slug = ?
            """,
            (business_id, provider_slug),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE integration_connections
                SET auth_type = 'api_key',
                    status = 'connected',
                    secret_ciphertext = ?,
                    credential_hint = ?,
                    provider_name = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    ciphertext,
                    hint,
                    integration["name"],
                    now,
                    existing["id"],
                ),
            )
            connection_id = existing["id"]
        else:
            conn.execute(
                """
                INSERT INTO integration_connections (
                    id, account_id, business_id, provider_slug, provider_name,
                    auth_type, status, secret_ciphertext, credential_hint,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'api_key', 'connected', ?, ?, ?, ?)
                """,
                (
                    connection_id,
                    account_id,
                    business_id,
                    provider_slug,
                    integration["name"],
                    ciphertext,
                    hint,
                    now,
                    now,
                ),
            )
        conn.commit()

    conn_row = get_connection(account_id, connection_id)
    if not conn_row:
        raise RuntimeError("failed to save connection")
    return conn_row


def connect_oauth_tokens(
    account_id: str,
    business_id: str,
    *,
    provider_slug: str,
    credentials: dict[str, Any],
    credential_hint: str,
) -> dict[str, Any]:
    if not business_store.get_business(account_id, business_id):
        raise LookupError("business not found")
    integration = get_integration(provider_slug)
    if not integration:
        raise ValueError("unknown provider")

    now = _utc_now()
    ciphertext = integration_secrets.encrypt_credentials(credentials)
    hint = credential_hint.strip() or credentials.get("hint") or "oauth connected"
    connection_id = str(uuid.uuid4())

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM integration_connections
            WHERE business_id = ? AND provider_slug = ?
            """,
            (business_id, provider_slug),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE integration_connections
                SET auth_type = 'oauth',
                    status = 'connected',
                    secret_ciphertext = ?,
                    credential_hint = ?,
                    provider_name = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    ciphertext,
                    hint,
                    integration["name"],
                    now,
                    existing["id"],
                ),
            )
            connection_id = existing["id"]
        else:
            conn.execute(
                """
                INSERT INTO integration_connections (
                    id, account_id, business_id, provider_slug, provider_name,
                    auth_type, status, secret_ciphertext, credential_hint,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'oauth', 'connected', ?, ?, ?, ?)
                """,
                (
                    connection_id,
                    account_id,
                    business_id,
                    provider_slug,
                    integration["name"],
                    ciphertext,
                    hint,
                    now,
                    now,
                ),
            )
        conn.commit()

    conn_row = get_connection(account_id, connection_id)
    if not conn_row:
        raise RuntimeError("failed to save connection")
    return conn_row


def connect_oauth_pending(
    account_id: str,
    business_id: str,
    *,
    provider_slug: str,
) -> dict[str, Any]:
    if not business_store.get_business(account_id, business_id):
        raise LookupError("business not found")
    integration = get_integration(provider_slug)
    if not integration:
        raise ValueError("unknown provider")

    now = _utc_now()
    connection_id = str(uuid.uuid4())
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM integration_connections
            WHERE business_id = ? AND provider_slug = ?
            """,
            (business_id, provider_slug),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE integration_connections
                SET auth_type = 'oauth',
                    status = 'pending',
                    secret_ciphertext = NULL,
                    credential_hint = '',
                    provider_name = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (integration["name"], now, existing["id"]),
            )
            connection_id = existing["id"]
        else:
            conn.execute(
                """
                INSERT INTO integration_connections (
                    id, account_id, business_id, provider_slug, provider_name,
                    auth_type, status, secret_ciphertext, credential_hint,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'oauth', 'pending', NULL, '', ?, ?)
                """,
                (
                    connection_id,
                    account_id,
                    business_id,
                    provider_slug,
                    integration["name"],
                    now,
                    now,
                ),
            )
        conn.commit()
    conn_row = get_connection(account_id, connection_id)
    if not conn_row:
        raise RuntimeError("failed to save connection")
    return conn_row


def delete_connection(account_id: str, business_id: str, connection_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """
            DELETE FROM integration_connections
            WHERE account_id = ? AND business_id = ? AND id = ?
            """,
            (account_id, business_id, connection_id),
        )
        conn.commit()
        return cur.rowcount > 0
