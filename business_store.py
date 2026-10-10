"""Business workspace persistence (scoped to an account)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app_db import connect, init_app_database

_ACTIVE_FILTER = "archived_at IS NULL"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def ensure_account(account_id: str) -> None:
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO accounts (id, created_at)
            VALUES (?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (account_id, now),
        )
        conn.commit()


def list_businesses(account_id: str, *, include_archived: bool = False) -> list[dict[str, Any]]:
    where = "account_id = ?"
    if not include_archived:
        where += f" AND {_ACTIVE_FILTER}"
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, name, industry, health, last_activity, created_at, updated_at, archived_at
            FROM businesses
            WHERE {where}
            ORDER BY updated_at DESC
            """,
            (account_id,),
        ).fetchall()
    return [_row_to_business(row) for row in rows]


def get_business(
    account_id: str,
    business_id: str,
    *,
    include_archived: bool = False,
) -> dict[str, Any] | None:
    where = "account_id = ? AND id = ?"
    if not include_archived:
        where += f" AND {_ACTIVE_FILTER}"
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT id, name, industry, health, last_activity, created_at, updated_at, archived_at
            FROM businesses
            WHERE {where}
            """,
            (account_id, business_id),
        ).fetchone()
    return _row_to_business(row) if row else None


def create_business(
    account_id: str,
    *,
    name: str,
    industry: str = "",
) -> dict[str, Any]:
    ensure_account(account_id)
    business_id = str(uuid.uuid4())
    now = _utc_now()
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("name is required")
    clean_industry = industry.strip()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO businesses (
                id, account_id, name, industry, health, last_activity, created_at, updated_at, archived_at
            )
            VALUES (?, ?, ?, ?, 'healthy', ?, ?, ?, NULL)
            """,
            (business_id, account_id, clean_name, clean_industry, "Just created", now, now),
        )
        conn.commit()
    business = get_business(account_id, business_id)
    if not business:
        raise RuntimeError("failed to create business")
    try:
        import account_activity_store

        account_activity_store.record(
            account_id,
            category="business",
            action="created",
            summary=f"Business created · {clean_name}",
            detail={"business_id": business_id, "industry": clean_industry},
        )
    except Exception:
        pass
    return business


def update_business(
    account_id: str,
    business_id: str,
    *,
    name: str | None = None,
    industry: str | None = None,
    archived: bool | None = None,
) -> dict[str, Any] | None:
    existing = get_business(account_id, business_id, include_archived=True)
    if not existing:
        return None

    fields: list[str] = []
    values: list[Any] = []

    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("name cannot be empty")
        fields.append("name = ?")
        values.append(clean_name)

    if industry is not None:
        fields.append("industry = ?")
        values.append(industry.strip())

    if archived is not None:
        fields.append("archived_at = ?")
        values.append(_utc_now() if archived else None)

    if not fields:
        return existing

    now = _utc_now()
    fields.append("updated_at = ?")
    values.append(now)
    values.extend([account_id, business_id])

    with connect() as conn:
        cur = conn.execute(
            f"""
            UPDATE businesses
            SET {", ".join(fields)}
            WHERE account_id = ? AND id = ?
            """,
            values,
        )
        conn.commit()
        if cur.rowcount == 0:
            return None

    return get_business(account_id, business_id, include_archived=True)


def delete_business(account_id: str, business_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM businesses WHERE account_id = ? AND id = ?",
            (account_id, business_id),
        )
        conn.commit()
        return cur.rowcount > 0


def _row_to_business(row: Any) -> dict[str, Any]:
    industry = row["industry"] or ""
    return {
        "id": row["id"],
        "name": row["name"],
        "industry": industry if industry else "—",
        "industry_raw": industry,
        "health": row["health"],
        "last_activity": row["last_activity"] or "—",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "archived": bool(row["archived_at"]),
        "archived_at": row["archived_at"],
    }
