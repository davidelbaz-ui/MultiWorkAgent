"""Persistence for agent threads, messages, and composer drafts."""

from __future__ import annotations

import secrets
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chat_db import STORAGE_DIR, connect, init_chat_database

CHAT_FILES_DIR = STORAGE_DIR / "chat_files"
MAX_DRAFT_FILE_BYTES = 25 * 1024 * 1024


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _thread_dir(thread_id: str) -> Path:
    return CHAT_FILES_DIR / thread_id


def ensure_thread(
    thread_id: str,
    *,
    workspace_id: str | None = None,
    kind: str = "main",
    title: str = "Main chat",
) -> None:
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_threads (id, created_at, updated_at, workspace_id, kind, title)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (thread_id, now, now, workspace_id, kind, title),
        )
        conn.execute(
            """
            INSERT INTO chat_drafts (thread_id, body, updated_at)
            VALUES (?, '', ?)
            ON CONFLICT(thread_id) DO NOTHING
            """,
            (thread_id, now),
        )
        conn.commit()
    _thread_dir(thread_id).mkdir(parents=True, exist_ok=True)


def list_messages(thread_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()
    return [dict(row) for row in rows]


MAX_INLINE_IMAGE_BYTES = 7 * 1024 * 1024
MAX_INLINE_TEXT_BYTES = 512 * 1024


def is_text_like_attachment(mime_type: str | None, original_name: str) -> bool:
    mime = (mime_type or "").lower()
    if mime.startswith("text/"):
        return True
    if mime in (
        "application/json",
        "application/xml",
        "application/x-yaml",
        "application/yaml",
        "application/javascript",
    ):
        return True
    lower = original_name.lower()
    for ext in (".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".log"):
        if lower.endswith(ext):
            return True
    return False


def read_message_attachment_bytes(
    *,
    thread_id: str,
    message_id: int,
    file_id: int,
    max_bytes: int | None = None,
) -> tuple[bytes, str] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT mf.stored_name, mf.mime_type, mf.size_bytes
            FROM chat_message_files mf
            JOIN chat_messages m ON m.id = mf.message_id
            WHERE mf.id = ? AND mf.message_id = ? AND m.thread_id = ?
            """,
            (file_id, message_id, thread_id),
        ).fetchone()
    if not row:
        return None
    limit = MAX_INLINE_IMAGE_BYTES if max_bytes is None else max_bytes
    if int(row["size_bytes"] or 0) > limit:
        return None
    path = _thread_dir(thread_id) / row["stored_name"]
    if not path.is_file():
        return None
    mime = (row["mime_type"] or "application/octet-stream").strip()
    return path.read_bytes(), mime


def get_message_files(message_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, original_name, size_bytes, mime_type
            FROM chat_message_files
            WHERE message_id = ?
            ORDER BY id ASC
            """,
            (message_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_draft(thread_id: str) -> dict[str, Any]:
    with connect() as conn:
        draft = conn.execute(
            "SELECT body, updated_at FROM chat_drafts WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        files = conn.execute(
            """
            SELECT id, original_name, size_bytes, mime_type, created_at
            FROM chat_draft_files
            WHERE thread_id = ?
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()
    return {
        "body": draft["body"] if draft else "",
        "updated_at": draft["updated_at"] if draft else None,
        "files": [dict(row) for row in files],
    }


def set_draft_body(thread_id: str, body: str) -> None:
    now = _utc_now()
    ensure_thread(thread_id)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_drafts (thread_id, body, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                body = excluded.body,
                updated_at = excluded.updated_at
            """,
            (thread_id, body, now),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()


def add_draft_file(
    thread_id: str,
    *,
    original_name: str,
    mime_type: str | None,
    size_bytes: int,
    data: bytes,
) -> dict[str, Any]:
    if size_bytes > MAX_DRAFT_FILE_BYTES:
        raise ValueError("File exceeds maximum upload size (25 MB).")

    ensure_thread(thread_id)
    stored_name = f"{uuid.uuid4().hex}_{secrets.token_hex(4)}"
    dest = _thread_dir(thread_id) / stored_name
    dest.write_bytes(data)

    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_draft_files (
                thread_id, stored_name, original_name, mime_type, size_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (thread_id, stored_name, original_name, mime_type, size_bytes, now),
        )
        file_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()

    return {
        "id": file_id,
        "original_name": original_name,
        "size_bytes": size_bytes,
        "mime_type": mime_type,
    }


def remove_draft_file(thread_id: str, file_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT stored_name FROM chat_draft_files
            WHERE id = ? AND thread_id = ?
            """,
            (file_id, thread_id),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "DELETE FROM chat_draft_files WHERE id = ? AND thread_id = ?",
            (file_id, thread_id),
        )
        conn.commit()

    path = _thread_dir(thread_id) / row["stored_name"]
    path.unlink(missing_ok=True)
    return True


def create_user_message(thread_id: str, content: str) -> dict[str, Any]:
    ensure_thread(thread_id)
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_messages (thread_id, role, content, created_at)
            VALUES (?, 'user', ?, ?)
            """,
            (thread_id, content, now),
        )
        message_id = int(cur.lastrowid)

        draft_files = conn.execute(
            """
            SELECT id, stored_name, original_name, mime_type, size_bytes
            FROM chat_draft_files
            WHERE thread_id = ?
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()

        for row in draft_files:
            conn.execute(
                """
                INSERT INTO chat_message_files (
                    message_id, stored_name, original_name, mime_type, size_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    row["stored_name"],
                    row["original_name"],
                    row["mime_type"],
                    row["size_bytes"],
                    now,
                ),
            )
            conn.execute(
                "DELETE FROM chat_draft_files WHERE id = ?",
                (row["id"],),
            )

        conn.execute(
            """
            UPDATE chat_drafts SET body = '', updated_at = ?
            WHERE thread_id = ?
            """,
            (now, thread_id),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()

    attachments = get_message_files(message_id)
    return {
        "id": message_id,
        "role": "user",
        "content": content,
        "created_at": now,
        "attachments": attachments,
    }


def get_user_message(thread_id: str, message_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, role, content, created_at
            FROM chat_messages
            WHERE id = ? AND thread_id = ?
            """,
            (message_id, thread_id),
        ).fetchone()
    if not row or row["role"] != "user":
        return None
    msg = dict(row)
    msg["attachments"] = get_message_files(int(msg["id"]))
    return msg


def update_user_message(thread_id: str, message_id: int, content: str) -> dict[str, Any] | None:
    if not get_user_message(thread_id, message_id):
        return None
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE chat_messages
            SET content = ?
            WHERE id = ? AND thread_id = ? AND role = 'user'
            """,
            (content, message_id, thread_id),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()
    return get_user_message(thread_id, message_id)


def delete_user_message(thread_id: str, message_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT role FROM chat_messages
            WHERE id = ? AND thread_id = ?
            """,
            (message_id, thread_id),
        ).fetchone()
        if not row or row["role"] != "user":
            return False
        files = conn.execute(
            "SELECT stored_name FROM chat_message_files WHERE message_id = ?",
            (message_id,),
        ).fetchall()
        conn.execute(
            "DELETE FROM chat_messages WHERE id = ? AND thread_id = ?",
            (message_id, thread_id),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (_utc_now(), thread_id),
        )
        conn.commit()

    for file_row in files:
        (_thread_dir(thread_id) / file_row["stored_name"]).unlink(missing_ok=True)
    return True


def create_system_message(thread_id: str, content: str) -> dict[str, Any]:
    ensure_thread(thread_id)
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_messages (thread_id, role, content, created_at)
            VALUES (?, 'system', ?, ?)
            """,
            (thread_id, content, now),
        )
        message_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()
    return {
        "id": message_id,
        "role": "system",
        "content": content,
        "created_at": now,
    }


def create_agent_message(thread_id: str, content: str) -> dict[str, Any]:
    ensure_thread(thread_id)
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_messages (thread_id, role, content, created_at)
            VALUES (?, 'agent', ?, ?)
            """,
            (thread_id, content, now),
        )
        message_id = int(cur.lastrowid)
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()
    return {
        "id": message_id,
        "role": "agent",
        "content": content,
        "created_at": now,
    }


def get_thread_meta(thread_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, workspace_id, kind, title, created_at, updated_at
            FROM chat_threads WHERE id = ?
            """,
            (thread_id,),
        ).fetchone()
    return dict(row) if row else None


def get_thread_state(thread_id: str) -> dict[str, Any]:
    ensure_thread(thread_id)
    messages = list_messages(thread_id)
    for msg in messages:
        msg["attachments"] = get_message_files(int(msg["id"]))
    meta = get_thread_meta(thread_id) or {}
    return {
        "thread_id": thread_id,
        "title": meta.get("title") or "Main chat",
        "kind": meta.get("kind") or "main",
        "messages": messages,
        "draft": get_draft(thread_id),
    }


def create_workspace_with_main(workspace_id: str) -> str:
    main_id = str(uuid.uuid4())
    ensure_thread(main_id, workspace_id=workspace_id, kind="main", title="Main chat")
    return main_id


def adopt_legacy_thread(thread_id: str, workspace_id: str) -> None:
    ensure_thread(thread_id, workspace_id=workspace_id, kind="main", title="Main chat")
    with connect() as conn:
        conn.execute(
            """
            UPDATE chat_threads
            SET workspace_id = ?, kind = 'main', title = COALESCE(title, 'Main chat')
            WHERE id = ?
            """,
            (workspace_id, thread_id),
        )
        conn.commit()


def list_workspace_threads(workspace_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, title, created_at, updated_at
            FROM chat_threads
            WHERE workspace_id = ?
            ORDER BY CASE kind WHEN 'main' THEN 0 ELSE 1 END, created_at ASC
            """,
            (workspace_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def _side_chat_title(workspace_id: str) -> str:
    with connect() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM chat_threads WHERE workspace_id = ? AND kind = 'side'",
            (workspace_id,),
        ).fetchone()["c"]
    return f"Side chat {int(count) + 1}"


def create_side_thread(workspace_id: str, title: str | None = None) -> dict[str, Any]:
    thread_id = str(uuid.uuid4())
    label = title.strip() if title and title.strip() else _side_chat_title(workspace_id)
    ensure_thread(thread_id, workspace_id=workspace_id, kind="side", title=label)
    meta = get_thread_meta(thread_id)
    return meta or {"id": thread_id, "kind": "side", "title": label}


def rename_thread(workspace_id: str, thread_id: str, title: str) -> dict[str, Any] | None:
    clean = title.strip()
    if not clean:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM chat_threads WHERE id = ? AND workspace_id = ?",
            (thread_id, workspace_id),
        ).fetchone()
        if not row:
            return None
        now = _utc_now()
        conn.execute(
            "UPDATE chat_threads SET title = ?, updated_at = ? WHERE id = ?",
            (clean, now, thread_id),
        )
        conn.commit()
    return get_thread_meta(thread_id)


def clear_main_thread(workspace_id: str) -> dict[str, Any] | None:
    """Remove all messages and draft content from the workspace main thread."""
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM chat_threads
            WHERE workspace_id = ? AND kind = 'main'
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
        if not row:
            return None
        thread_id = row["id"]
        files = conn.execute(
            """
            SELECT stored_name FROM chat_message_files mf
            JOIN chat_messages m ON m.id = mf.message_id
            WHERE m.thread_id = ?
            """,
            (thread_id,),
        ).fetchall()
        draft_files = conn.execute(
            "SELECT stored_name FROM chat_draft_files WHERE thread_id = ?",
            (thread_id,),
        ).fetchall()
        conn.execute("DELETE FROM chat_messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM chat_draft_files WHERE thread_id = ?", (thread_id,))
        now = _utc_now()
        conn.execute(
            """
            UPDATE chat_drafts
            SET body = '', updated_at = ?
            WHERE thread_id = ?
            """,
            (now, thread_id),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
        conn.commit()

    folder = _thread_dir(thread_id)
    for file_row in files + draft_files:
        (folder / file_row["stored_name"]).unlink(missing_ok=True)
    meta = get_thread_meta(thread_id)
    return meta


def delete_side_thread(workspace_id: str, thread_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT kind FROM chat_threads WHERE id = ? AND workspace_id = ?",
            (thread_id, workspace_id),
        ).fetchone()
        if not row or row["kind"] != "side":
            return False
        files = conn.execute(
            """
            SELECT stored_name FROM chat_message_files mf
            JOIN chat_messages m ON m.id = mf.message_id
            WHERE m.thread_id = ?
            """,
            (thread_id,),
        ).fetchall()
        draft_files = conn.execute(
            "SELECT stored_name FROM chat_draft_files WHERE thread_id = ?",
            (thread_id,),
        ).fetchall()
        conn.execute("DELETE FROM chat_threads WHERE id = ?", (thread_id,))
        conn.commit()

    folder = _thread_dir(thread_id)
    for file_row in files + draft_files:
        (folder / file_row["stored_name"]).unlink(missing_ok=True)
    if folder.exists() and not any(folder.iterdir()):
        folder.rmdir()
    return True


def delete_workspace(workspace_id: str) -> None:
    threads = list_workspace_threads(workspace_id)
    stored_files: list[tuple[str, str]] = []
    with connect() as conn:
        for thread in threads:
            thread_id = thread["id"]
            rows = conn.execute(
                """
                SELECT stored_name FROM chat_message_files mf
                JOIN chat_messages m ON m.id = mf.message_id
                WHERE m.thread_id = ?
                """,
                (thread_id,),
            ).fetchall()
            stored_files.extend((thread_id, row["stored_name"]) for row in rows)
            draft_rows = conn.execute(
                "SELECT stored_name FROM chat_draft_files WHERE thread_id = ?",
                (thread_id,),
            ).fetchall()
            stored_files.extend((thread_id, row["stored_name"]) for row in draft_rows)
            conn.execute("DELETE FROM chat_threads WHERE id = ?", (thread_id,))
        conn.commit()

    seen_dirs: set[str] = set()
    for thread_id, stored_name in stored_files:
        ( _thread_dir(thread_id) / stored_name).unlink(missing_ok=True)
        seen_dirs.add(thread_id)
    for thread_id in seen_dirs:
        folder = _thread_dir(thread_id)
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()


def delete_workspaces(workspace_ids: list[str]) -> None:
    for workspace_id in workspace_ids:
        if workspace_id:
            delete_workspace(workspace_id)


def get_workspace_state(workspace_id: str, active_thread_id: str) -> dict[str, Any]:
    state = get_thread_state(active_thread_id)
    state["workspace_id"] = workspace_id
    state["active_thread_id"] = active_thread_id
    state["threads"] = list_workspace_threads(workspace_id)
    return state


def bootstrap() -> None:
    init_chat_database()
