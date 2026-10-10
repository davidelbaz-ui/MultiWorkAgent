"""Support message file attachments on disk + metadata in PostgreSQL."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage_paths import storage_dir
from support_db import connect

SUPPORT_FILES_DIR = storage_dir() / "support_files"
MAX_SUPPORT_FILE_BYTES = 25 * 1024 * 1024
MAX_FILES_PER_MESSAGE = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_storage() -> None:
    SUPPORT_FILES_DIR.mkdir(parents=True, exist_ok=True)


def _account_dir(account_id: str) -> Path:
    path = SUPPORT_FILES_DIR / account_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_attachments(
    *,
    account_id: str,
    message_id: str,
    files: list[tuple[str, str | None, bytes]],
) -> list[dict[str, Any]]:
    if len(files) > MAX_FILES_PER_MESSAGE:
        raise ValueError(f"At most {MAX_FILES_PER_MESSAGE} files per message.")
    ensure_storage()
    saved: list[dict[str, Any]] = []
    now = _utc_now()
    dest_dir = _account_dir(account_id)
    with connect() as conn:
        for original_name, mime_type, data in files:
            if len(data) > MAX_SUPPORT_FILE_BYTES:
                raise ValueError("File exceeds maximum upload size (25 MB).")
            clean_name = (original_name or "file").strip() or "file"
            stored_name = f"{uuid.uuid4().hex}_{secrets.token_hex(4)}"
            (dest_dir / stored_name).write_bytes(data)
            att_id = uuid.uuid4().hex
            conn.execute(
                """
                INSERT INTO support_message_attachments (
                    id, account_id, message_id, stored_name, original_name,
                    mime_type, size_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    att_id,
                    account_id,
                    message_id,
                    stored_name,
                    clean_name,
                    mime_type,
                    len(data),
                    now,
                ),
            )
            saved.append(
                {
                    "id": att_id,
                    "original_name": clean_name,
                    "mime_type": mime_type,
                    "size_bytes": len(data),
                }
            )
        conn.commit()
    return saved


def attachments_by_message_ids(message_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not message_ids:
        return {}
    placeholders = ",".join("?" for _ in message_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, message_id, original_name, mime_type, size_bytes, created_at
            FROM support_message_attachments
            WHERE message_id IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            """,
            tuple(message_ids),
        ).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        item = {
            "id": row["id"],
            "original_name": row["original_name"],
            "mime_type": row["mime_type"],
            "size_bytes": int(row["size_bytes"]),
            "created_at": row["created_at"],
        }
        out.setdefault(row["message_id"], []).append(item)
    return out


def get_attachment_row(account_id: str, attachment_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, message_id, stored_name, original_name, mime_type, size_bytes
            FROM support_message_attachments
            WHERE account_id = ? AND id = ?
            """,
            (account_id, attachment_id),
        ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "message_id": row["message_id"],
        "stored_name": row["stored_name"],
        "original_name": row["original_name"],
        "mime_type": row["mime_type"],
        "size_bytes": int(row["size_bytes"]),
    }


def attachment_path(account_id: str, stored_name: str) -> Path:
    return _account_dir(account_id) / stored_name
