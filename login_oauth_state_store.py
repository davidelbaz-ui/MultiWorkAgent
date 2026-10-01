"""One-time OAuth state tokens for login (Google / Microsoft)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from app_db import connect, init_app_database

STATE_TTL_SECONDS = 900


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _cleanup_expired(conn) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=STATE_TTL_SECONDS)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat()
    conn.execute("DELETE FROM login_oauth_states WHERE created_at < ?", (cutoff_iso,))


def create_state(*, provider: str, next_url: str = "") -> str:
    token = secrets.token_urlsafe(32)
    now = _utc_now()
    with connect() as conn:
        _cleanup_expired(conn)
        conn.execute(
            """
            INSERT INTO login_oauth_states (state_token, provider, next_url, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (token, provider, next_url, now),
        )
        conn.commit()
    return token


def pop_state(state_token: str) -> dict[str, str] | None:
    if not state_token:
        return None
    with connect() as conn:
        _cleanup_expired(conn)
        row = conn.execute(
            """
            SELECT state_token, provider, next_url, created_at
            FROM login_oauth_states
            WHERE state_token = ?
            """,
            (state_token,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM login_oauth_states WHERE state_token = ?", (state_token,))
        conn.commit()
    return {
        "state_token": row["state_token"],
        "provider": row["provider"],
        "next_url": row["next_url"] or "",
        "created_at": row["created_at"],
    }
