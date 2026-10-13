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

def support_reminder_text() -> str:
    """Static copy shown in the UI — not stored as a thread message."""
    return (
        "Thanks for reaching out. Our team typically replies within "
        f"{SUPPORT_SLA_HOURS} hours on business days. "
        "Describe your issue below — include screenshots or error messages if you can."
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bootstrap() -> None:
    from app_db import init_app_database
    import support_attachments

    init_app_database()
    support_attachments.ensure_storage()


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


def get_thread(account_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, status, created_at, updated_at
            FROM support_threads
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_or_create_thread(account_id: str) -> dict[str, Any]:
    existing = get_thread(account_id)
    if existing:
        return existing
    now = _utc_now()
    with connect() as conn:
        thread_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO support_threads (id, account_id, status, created_at, updated_at)
            VALUES (?, ?, 'open', ?, ?)
            """,
            (thread_id, account_id, now, now),
        )
        conn.commit()
    return {
        "id": thread_id,
        "account_id": account_id,
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }


def _delete_thread_if_empty(account_id: str, thread_id: str) -> None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM support_messages
            WHERE thread_id = ?
              AND sender_type != ?
            """,
            (thread_id, SENDER_SYSTEM),
        ).fetchone()
        if row and int(row["n"]) > 0:
            return
        conn.execute("DELETE FROM support_threads WHERE id = ?", (thread_id,))
        conn.commit()


def list_messages(account_id: str) -> list[dict[str, Any]]:
    thread = get_thread(account_id)
    if not thread:
        return []
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, thread_id, sender_type, author_user_id, body, created_at
            FROM support_messages
            WHERE thread_id = ?
              AND sender_type != ?
            ORDER BY created_at ASC, id ASC
            """,
            (thread["id"], SENDER_SYSTEM),
        ).fetchall()
    if not rows:
        _delete_thread_if_empty(account_id, thread["id"])
        return []
    messages = [_row_to_message(row) for row in rows]
    _attach_files_to_messages(messages)
    return messages


def _attach_files_to_messages(messages: list[dict[str, Any]]) -> None:
    if not messages:
        return
    import support_attachments

    ids = [m["id"] for m in messages]
    by_msg = support_attachments.attachments_by_message_ids(ids)
    for msg in messages:
        msg["attachments"] = by_msg.get(msg["id"], [])


def _validate_body(body: str, *, allow_empty: bool = False) -> str:
    clean = (body or "").strip()
    if not clean and not allow_empty:
        raise ValueError("Message cannot be empty.")
    if len(clean) > MAX_MESSAGE_BODY_LEN:
        raise ValueError(f"Message must be at most {MAX_MESSAGE_BODY_LEN} characters.")
    return clean


def add_user_message(
    *,
    account_id: str,
    user_id: str,
    body: str,
    attachment_files: list[tuple[str, str | None, bytes]] | None = None,
) -> dict[str, Any]:
    files = attachment_files or []
    clean = _validate_body(body, allow_empty=bool(files))
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
    msg = _row_to_message(row)
    if files:
        import support_attachments

        msg["attachments"] = support_attachments.save_attachments(
            account_id=account_id,
            message_id=message_id,
            files=files,
        )
    else:
        msg["attachments"] = []
    try:
        import account_activity_store

        account_activity_store.record(
            account_id,
            category="support",
            action="user_message",
            summary="Support message from user",
            user_id=user_id,
            detail={
                "preview": clean[:160],
                "attachment_count": len(files),
            },
        )
    except Exception:
        pass
    return msg


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


def set_thread_status(account_id: str, status: str) -> None:
    clean = (status or "").strip().lower()
    if clean not in ("open", "closed"):
        raise ValueError("status must be open or closed")
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE support_threads
            SET status = ?, updated_at = ?
            WHERE account_id = ?
            """,
            (clean, now, account_id),
        )
        conn.commit()


def list_inbox(*, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    cap = max(1, min(limit, 200))
    where_parts: list[str] = []
    query_params: list[Any] = [SENDER_USER, SENDER_SYSTEM]
    if status:
        where_parts.append("t.status = ?")
        query_params.append(status.strip().lower())
    where_parts.append(
        """
        EXISTS (
            SELECT 1
            FROM support_messages m
            WHERE m.thread_id = t.id
              AND m.sender_type != ?
        )
        """.strip()
    )
    query_params.append(SENDER_SYSTEM)
    query_params.append(cap)
    where = "WHERE " + " AND ".join(where_parts)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                t.id AS thread_id,
                t.account_id,
                t.status,
                t.created_at,
                t.updated_at,
                u.email AS owner_email,
                u.display_name AS owner_name,
                (
                    SELECT COUNT(*)
                    FROM support_messages m
                    WHERE m.thread_id = t.id AND m.sender_type = ?
                ) AS user_message_count,
                (
                    SELECT body
                    FROM support_messages m
                    WHERE m.thread_id = t.id
                      AND m.sender_type != ?
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT 1
                ) AS last_snippet
            FROM support_threads t
            LEFT JOIN account_members am
                ON am.account_id = t.account_id AND am.role = 'owner'
            LEFT JOIN users u ON u.id = am.user_id
            {where}
            ORDER BY t.updated_at DESC
            LIMIT ?
            """,
            tuple(query_params),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        snippet = (row["last_snippet"] or "")[:240]
        out.append(
            {
                "thread_id": row["thread_id"],
                "account_id": row["account_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "owner_email": row["owner_email"] or "",
                "owner_name": row["owner_name"] or "",
                "user_message_count": int(row["user_message_count"] or 0),
                "last_snippet": snippet,
            }
        )
    return out


def message_to_api(
    row: dict[str, Any],
    *,
    viewer_user_id: str | None = None,
    account_id: str | None = None,
    for_admin: bool = False,
) -> dict[str, Any]:
    sender = row["sender_type"]
    if sender == SENDER_SUPPORT:
        label = "Support"
    elif sender == SENDER_SYSTEM:
        label = "MultiWorkAgent"
    elif viewer_user_id and row.get("author_user_id") == viewer_user_id:
        label = "You"
    else:
        label = "Team member"
    attachments_out: list[dict[str, Any]] = []
    for att in row.get("attachments") or []:
        att_id = att.get("id")
        if not att_id:
            continue
        if for_admin and account_id:
            url = f"/admin/support/{account_id}/attachments/{att_id}"
        elif account_id:
            url = f"/api/support/attachments/{att_id}"
        else:
            url = ""
        attachments_out.append(
            {
                "id": att_id,
                "original_name": att.get("original_name") or "file",
                "mime_type": att.get("mime_type"),
                "size_bytes": att.get("size_bytes"),
                "url": url,
            }
        )

    return {
        "id": row["id"],
        "sender_type": sender,
        "sender_label": label,
        "body": row["body"],
        "created_at": row["created_at"],
        "is_mine": sender == SENDER_USER
        and bool(viewer_user_id)
        and row.get("author_user_id") == viewer_user_id,
        "attachments": attachments_out,
    }
