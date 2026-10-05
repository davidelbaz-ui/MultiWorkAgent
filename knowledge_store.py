"""Per-business knowledge files (uploaded reference documents for the agent)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import business_store
from app_db import connect, init_app_database
from storage_paths import storage_dir

KNOWLEDGE_FILES_DIR = storage_dir() / "knowledge_files"
MAX_KNOWLEDGE_FILE_BYTES = 25 * 1024 * 1024
MAX_AGENT_KNOWLEDGE_CHARS = 80_000
MAX_AGENT_TEXT_ATTACHMENT_CHARS = 100_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()
    KNOWLEDGE_FILES_DIR.mkdir(parents=True, exist_ok=True)


def _business_dir(business_id: str) -> Path:
    return KNOWLEDGE_FILES_DIR / business_id


def list_files(account_id: str, *, business_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, original_name, mime_type, size_bytes, created_at
            FROM business_knowledge_files
            WHERE account_id = ? AND business_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (account_id, business_id),
        ).fetchall()
    return [dict(row) for row in rows]


def file_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "original_name": row["original_name"],
        "mime_type": row.get("mime_type"),
        "size_bytes": row["size_bytes"],
        "created_at": row["created_at"],
    }


def add_file(
    account_id: str,
    business_id: str,
    *,
    original_name: str,
    mime_type: str | None,
    size_bytes: int,
    data: bytes,
) -> dict[str, Any]:
    if not business_store.get_business(account_id, business_id):
        raise LookupError("business not found")
    if size_bytes > MAX_KNOWLEDGE_FILE_BYTES:
        raise ValueError("File exceeds maximum upload size (25 MB).")

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}_{secrets.token_hex(4)}"
    dest_dir = _business_dir(business_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / stored_name).write_bytes(data)

    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO business_knowledge_files (
                id, account_id, business_id, original_name, stored_name,
                mime_type, size_bytes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                account_id,
                business_id,
                original_name,
                stored_name,
                mime_type,
                size_bytes,
                now,
            ),
        )
        conn.commit()

    return file_to_api(
        {
            "id": file_id,
            "original_name": original_name,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "created_at": now,
        }
    )


def delete_file(account_id: str, business_id: str, file_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT stored_name FROM business_knowledge_files
            WHERE id = ? AND account_id = ? AND business_id = ?
            """,
            (file_id, account_id, business_id),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            """
            DELETE FROM business_knowledge_files
            WHERE id = ? AND account_id = ? AND business_id = ?
            """,
            (file_id, account_id, business_id),
        )
        conn.commit()

    path = _business_dir(business_id) / row["stored_name"]
    path.unlink(missing_ok=True)
    return True


def _is_text_like(mime_type: str | None, original_name: str) -> bool:
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
    for ext in (".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".log", ".env"):
        if lower.endswith(ext):
            return True
    return False


def read_file_text(
    account_id: str,
    business_id: str,
    file_id: str,
    *,
    max_chars: int = MAX_AGENT_TEXT_ATTACHMENT_CHARS,
) -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT original_name, stored_name, mime_type, size_bytes
            FROM business_knowledge_files
            WHERE id = ? AND account_id = ? AND business_id = ?
            """,
            (file_id, account_id, business_id),
        ).fetchone()
    if not row:
        return None
    if not _is_text_like(row["mime_type"], row["original_name"]):
        return None
    if int(row["size_bytes"] or 0) > MAX_KNOWLEDGE_FILE_BYTES:
        return None
    path = _business_dir(business_id) / row["stored_name"]
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n… [truncated]"
    return text


def build_agent_knowledge_block(
    account_id: str,
    *,
    business_id: str | None,
    max_total_chars: int = MAX_AGENT_KNOWLEDGE_CHARS,
) -> str:
    if not business_id:
        return ""
    files = list_files(account_id, business_id=business_id)
    if not files:
        return ""

    sections: list[str] = []
    used = 0
    for meta in reversed(files):
        name = meta["original_name"]
        if not _is_text_like(meta.get("mime_type"), name):
            sections.append(
                f"--- {name} ---\n[Binary or unsupported type; filename only — ask the user to paste text if needed.]"
            )
            used += len(sections[-1])
            if used >= max_total_chars:
                break
            continue
        remaining = max_total_chars - used
        if remaining < 200:
            break
        body = read_file_text(
            account_id,
            business_id,
            meta["id"],
            max_chars=min(MAX_AGENT_TEXT_ATTACHMENT_CHARS, remaining),
        )
        if body is None:
            continue
        chunk = f"--- {name} ---\n{body}"
        sections.append(chunk)
        used += len(chunk)

    return "\n\n".join(sections)
