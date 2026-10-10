"""Persistent account activity log for admin and auditing."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app_db import connect, init_app_database


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def record(
    account_id: str,
    *,
    category: str,
    action: str,
    summary: str,
    user_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    if not account_id or not category or not action or not summary:
        return
    clean_summary = " ".join(summary.split())[:500]
    detail_json = json.dumps(detail, ensure_ascii=False, default=str) if detail else None
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO account_activity_events (
                id, account_id, user_id, category, action, summary, detail_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                account_id,
                user_id,
                category.strip().lower()[:64],
                action.strip().lower()[:64],
                clean_summary,
                detail_json,
                now,
            ),
        )
        conn.commit()


def list_for_account(
    account_id: str,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, account_id, user_id, category, action, summary, detail_json, created_at
            FROM account_activity_events
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (account_id, limit, offset),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        detail: dict[str, Any] | None = None
        if row["detail_json"]:
            try:
                parsed = json.loads(row["detail_json"])
                if isinstance(parsed, dict):
                    detail = parsed
            except json.JSONDecodeError:
                detail = None
        out.append(
            {
                "id": row["id"],
                "account_id": row["account_id"],
                "user_id": row["user_id"],
                "category": row["category"],
                "action": row["action"],
                "summary": row["summary"],
                "detail": detail,
                "created_at": row["created_at"],
            }
        )
    return out
