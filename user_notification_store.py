"""User-scoped notifications (e.g. team invites before workspace membership)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app_db import connect, init_app_database


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def create_notification(
    user_id: str,
    *,
    kind: str,
    title: str,
    body: str,
    href: str | None = None,
    invite_id: str | None = None,
    dedupe_key: str | None = None,
) -> dict[str, Any]:
    if dedupe_key:
        with connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM user_notifications
                WHERE user_id = ? AND dedupe_key = ?
                """,
                (user_id, dedupe_key),
            ).fetchone()
            if existing:
                return get_notification(user_id, existing["id"]) or {}

    now = _utc_now()
    notification_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_notifications (
                id, user_id, kind, title, body, href, invite_id, dedupe_key, read_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                notification_id,
                user_id,
                kind,
                title.strip(),
                body.strip(),
                href,
                invite_id,
                dedupe_key,
                now,
            ),
        )
        conn.commit()
    row = get_notification(user_id, notification_id)
    if not row:
        raise RuntimeError("failed to create user notification")
    return row


def _row_to_notification(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "href": row["href"],
        "invite_id": row["invite_id"],
        "dedupe_key": row["dedupe_key"],
        "read_at": row["read_at"],
        "created_at": row["created_at"],
        "is_read": bool(row["read_at"]),
        "scope": "user",
    }


def get_notification(user_id: str, notification_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, kind, title, body, href, invite_id, dedupe_key, read_at, created_at
            FROM user_notifications
            WHERE user_id = ? AND id = ?
            """,
            (user_id, notification_id),
        ).fetchone()
    return _row_to_notification(row) if row else None


def list_for_user(user_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, kind, title, body, href, invite_id, dedupe_key, read_at, created_at
            FROM user_notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [_row_to_notification(row) for row in rows]


def unread_count(user_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c FROM user_notifications
            WHERE user_id = ? AND read_at IS NULL
            """,
            (user_id,),
        ).fetchone()
    return int(row["c"]) if row else 0


def mark_read(user_id: str, notification_id: str) -> bool:
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE user_notifications
            SET read_at = COALESCE(read_at, ?)
            WHERE user_id = ? AND id = ?
            """,
            (now, user_id, notification_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_notification(user_id: str, notification_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM user_notifications WHERE user_id = ? AND id = ?",
            (user_id, notification_id),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_all(user_id: str) -> int:
    with connect() as conn:
        cur = conn.execute("DELETE FROM user_notifications WHERE user_id = ?", (user_id,))
        conn.commit()
        return int(cur.rowcount)


def notification_to_api(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "href": row["href"],
        "is_read": row["is_read"],
        "created_at": row["created_at"],
        "scope": "user",
    }
    if row.get("invite_id"):
        payload["invite_id"] = row["invite_id"]
        payload["actions"] = ["accept", "decline"]
    return payload
