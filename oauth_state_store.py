"""One-time OAuth state tokens (CSRF protection for provider redirects)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app_db import connect, init_app_database

STATE_TTL_SECONDS = 900


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _cleanup_expired(conn) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STATE_TTL_SECONDS)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat()
    conn.execute(
        "DELETE FROM integration_oauth_states WHERE created_at < ?",
        (cutoff_iso,),
    )


def create_state(
    *,
    account_id: str,
    business_id: str,
    provider_slug: str,
) -> str:
    token = secrets.token_urlsafe(32)
    now = _utc_now()
    with connect() as conn:
        _cleanup_expired(conn)
        conn.execute(
            """
            INSERT INTO integration_oauth_states (
                state_token, account_id, business_id, provider_slug, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (token, account_id, business_id, provider_slug, now),
        )
        conn.commit()
    return token


def pop_state(state_token: str) -> dict[str, Any] | None:
    if not state_token:
        return None
    with connect() as conn:
        _cleanup_expired(conn)
        row = conn.execute(
            """
            SELECT state_token, account_id, business_id, provider_slug, created_at
            FROM integration_oauth_states
            WHERE state_token = ?
            """,
            (state_token,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "DELETE FROM integration_oauth_states WHERE state_token = ?",
            (state_token,),
        )
        conn.commit()
    return {
        "state_token": row["state_token"],
        "account_id": row["account_id"],
        "business_id": row["business_id"],
        "provider_slug": row["provider_slug"],
        "created_at": row["created_at"],
    }
