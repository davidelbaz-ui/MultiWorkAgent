"""Contact support threads and messages (separate support.sqlite)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from support_db import connect

SUPPORT_SLA_HOURS = 48
MAX_MESSAGE_BODY_LEN = 8000
SENDER_USER = "user"
SENDER_SUPPORT = "support"
SENDER_SYSTEM = "system"

_WELCOME_BODY = (
    "Thanks for reaching out. Our team typically replies within "
    f"{SUPPORT_SLA_HOURS} hours on business days. "
    "Describe your issue below — include screenshots or error messages if you can."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bootstrap() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS support_threads (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_support_threads_account
                ON support_threads (account_id);

            CREATE TABLE IF NOT EXISTS support_messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                author_user_id TEXT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (thread_id) REFERENCES support_threads (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_support_messages_thread
                ON support_messages (thread_id, created_at ASC);
            """
        )
        conn.commit()


def delete_threads_for_account(account_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM support_threads WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        count = int(row["n"]) if row else 0
        conn.execute("DELETE FROM support_threads WHERE account_id = ?", (account_id,))
        conn.commit()
    return count


def _row_to_message(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "sender_type": row["sender_type"],
        "author_user_id": row["author_user_id"],
        "body": row["body"],
        "created_at": row["created_at"],
    }


def get_or_create_thread(account_id: str) -> dict[str, Any]:
    now = _utc_now()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, status, created_at, updated_at
            FROM support_threads
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
        if row:
            return {
                "id": row["id"],
                "account_id": row["account_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

        thread_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO support_threads (id, account_id, status, created_at, updated_at)
            VALUES (?, ?, 'open', ?, ?)
            """,
            (thread_id, account_id, now, now),
        )
        conn.execute(
            """
            INSERT INTO support_messages (
                id, thread_id, sender_type, author_user_id, body, created_at
            ) VALUES (?, ?, ?, NULL, ?, ?)
            """,
            (uuid.uuid4().hex, thread_id, SENDER_SYSTEM, _WELCOME_BODY, now),
        )
        conn.commit()
    return {
        "id": thread_id,
        "account_id": account_id,
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }


def list_messages(account_id: str) -> list[dict[str, Any]]:
    thread = get_or_create_thread(account_id)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, thread_id, sender_type, author_user_id, body, created_at
            FROM support_messages
            WHERE thread_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (thread["id"],),
        ).fetchall()
    return [_row_to_message(row) for row in rows]


def _validate_body(body: str) -> str:
    clean = (body or "").strip()
    if not clean:
        raise ValueError("Message cannot be empty.")
    if len(clean) > MAX_MESSAGE_BODY_LEN:
        raise ValueError(f"Message must be at most {MAX_MESSAGE_BODY_LEN} characters.")
    return clean


def add_user_message(*, account_id: str, user_id: str, body: str) -> dict[str, Any]:
    clean = _validate_body(body)
    thread = get_or_create_thread(account_id)
    now = _utc_now()
    message_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO support_messages (
                id, thread_id, sender_type, author_user_id, body, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, thread["id"], SENDER_USER, user_id, clean, now),
        )
        conn.execute(
            "UPDATE support_threads SET updated_at = ? WHERE id = ?",
            (now, thread["id"]),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, thread_id, sender_type, author_user_id, body, created_at
            FROM support_messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
    if not row:
        raise RuntimeError("failed to save support message")
    return _row_to_message(row)


def add_support_reply(*, account_id: str, body: str) -> dict[str, Any]:
    """Staff reply (not tied to an end-user id)."""
    clean = _validate_body(body)
    thread = get_or_create_thread(account_id)
    now = _utc_now()
    message_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO support_messages (
                id, thread_id, sender_type, author_user_id, body, created_at
            ) VALUES (?, ?, ?, NULL, ?, ?)
            """,
            (message_id, thread["id"], SENDER_SUPPORT, clean, now),
        )
        conn.execute(
            "UPDATE support_threads SET updated_at = ? WHERE id = ?",
            (now, thread["id"]),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, thread_id, sender_type, author_user_id, body, created_at
            FROM support_messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
    if not row:
        raise RuntimeError("failed to save support reply")
    return _row_to_message(row)


def message_to_api(row: dict[str, Any], *, viewer_user_id: str | None = None) -> dict[str, Any]:
    sender = row["sender_type"]
    if sender == SENDER_SUPPORT:
        label = "Support"
    elif sender == SENDER_SYSTEM:
        label = "MultiWorkAgent"
    elif viewer_user_id and row.get("author_user_id") == viewer_user_id:
        label = "You"
    else:
        label = "Team member"
    return {
        "id": row["id"],
        "sender_type": sender,
        "sender_label": label,
        "body": row["body"],
        "created_at": row["created_at"],
        "is_mine": sender == SENDER_USER
        and bool(viewer_user_id)
        and row.get("author_user_id") == viewer_user_id,
    }
