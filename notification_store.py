"""In-app notifications per account (bell feed)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg

import business_store
from app_db import connect, init_app_database

PREF_KEYS = (
    "run_done",
    "run_failed",
    "quota_warn",
    "quota_exhausted",
    "daily_breaker",
    "payment_issue",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def ensure_prefs(account_id: str) -> dict[str, bool]:
    business_store.ensure_account(account_id)
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO account_notification_prefs (
                account_id, run_done, run_failed, quota_warn, quota_exhausted,
                daily_breaker, payment_issue, updated_at
            ) VALUES (?, 1, 1, 1, 1, 1, 1, ?)
            ON CONFLICT(account_id) DO NOTHING
            """,
            (account_id, now),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT run_done, run_failed, quota_warn, quota_exhausted,
                   daily_breaker, payment_issue, updated_at
            FROM account_notification_prefs
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
    if not row:
        raise RuntimeError("notification prefs missing")
    return {
        "run_done": bool(row["run_done"]),
        "run_failed": bool(row["run_failed"]),
        "quota_warn": bool(row["quota_warn"]),
        "quota_exhausted": bool(row["quota_exhausted"]),
        "daily_breaker": bool(row["daily_breaker"]),
        "payment_issue": bool(row["payment_issue"]),
        "updated_at": row["updated_at"],
    }


def update_prefs(account_id: str, **kwargs: Any) -> dict[str, bool]:
    ensure_prefs(account_id)
    updates: dict[str, int] = {}
    for key in PREF_KEYS:
        if key in kwargs:
            updates[key] = 1 if kwargs[key] else 0
    if not updates:
        return ensure_prefs(account_id)
    now = _utc_now()
    sets = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [now, account_id]
    with connect() as conn:
        conn.execute(
            f"""
            UPDATE account_notification_prefs
            SET {sets}, updated_at = ?
            WHERE account_id = ?
            """,
            params,
        )
        conn.commit()
    return ensure_prefs(account_id)


def _pref_enabled(prefs: dict[str, bool], kind: str) -> bool:
    mapping = {
        "run_completed": "run_done",
        "run_failed": "run_failed",
        "quota_80": "quota_warn",
        "quota_100": "quota_exhausted",
        "daily_limit": "daily_breaker",
        "payment_issue": "payment_issue",
    }
    key = mapping.get(kind)
    if not key:
        return True
    return prefs.get(key, True)


def create_notification(
    account_id: str,
    *,
    kind: str,
    title: str,
    body: str,
    href: str | None = None,
    dedupe_key: str | None = None,
) -> dict[str, Any] | None:
    prefs = ensure_prefs(account_id)
    if not _pref_enabled(prefs, kind):
        return None

    if dedupe_key:
        with connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM account_notifications
                WHERE account_id = ? AND dedupe_key = ?
                """,
                (account_id, dedupe_key),
            ).fetchone()
            if existing:
                return get_notification(account_id, existing["id"])

    now = _utc_now()
    notification_id = str(uuid.uuid4())
    with connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO account_notifications (
                    id, account_id, kind, title, body, href, dedupe_key,
                    read_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    notification_id,
                    account_id,
                    kind,
                    title.strip(),
                    body.strip(),
                    href,
                    dedupe_key,
                    now,
                ),
            )
            conn.commit()
        except psycopg.errors.UniqueViolation:
            if dedupe_key:
                row = conn.execute(
                    """
                    SELECT id FROM account_notifications
                    WHERE account_id = ? AND dedupe_key = ?
                    """,
                    (account_id, dedupe_key),
                ).fetchone()
                if row:
                    return get_notification(account_id, row["id"])
            return None
    return get_notification(account_id, notification_id)


def _row_to_notification(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "href": row["href"],
        "dedupe_key": row["dedupe_key"],
        "read_at": row["read_at"],
        "created_at": row["created_at"],
        "is_read": bool(row["read_at"]),
    }


def get_notification(account_id: str, notification_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, kind, title, body, href, dedupe_key, read_at, created_at
            FROM account_notifications
            WHERE account_id = ? AND id = ?
            """,
            (account_id, notification_id),
        ).fetchone()
    return _row_to_notification(row) if row else None


def list_notifications(account_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, account_id, kind, title, body, href, dedupe_key, read_at, created_at
            FROM account_notifications
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
    return [_row_to_notification(row) for row in rows]


def unread_count(account_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM account_notifications
            WHERE account_id = ? AND read_at IS NULL
            """,
            (account_id,),
        ).fetchone()
    return int(row["c"]) if row else 0


def mark_read(account_id: str, notification_id: str) -> bool:
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE account_notifications
            SET read_at = COALESCE(read_at, ?)
            WHERE account_id = ? AND id = ?
            """,
            (now, account_id, notification_id),
        )
        conn.commit()
        return cur.rowcount > 0


def mark_all_read(account_id: str) -> int:
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE account_notifications
            SET read_at = ?
            WHERE account_id = ? AND read_at IS NULL
            """,
            (now, account_id),
        )
        conn.commit()
        return int(cur.rowcount)


def notification_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "href": row["href"],
        "is_read": row["is_read"],
        "created_at": row["created_at"],
    }
