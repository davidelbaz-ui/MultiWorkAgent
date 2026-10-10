"""Square payments and refunds cached per account."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import subscription_store
from app_db import connect, init_app_database


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _amount_from_payment(payment: dict[str, Any]) -> tuple[int, str]:
    money = payment.get("amount_money") or payment.get("total_money") or {}
    if isinstance(money, dict):
        cents = int(money.get("amount") or 0)
        currency = str(money.get("currency") or "USD")
        return cents, currency
    return 0, "USD"


def upsert_square_payment(account_id: str, payment: dict[str, Any]) -> dict[str, Any]:
    square_id = str(payment.get("id") or "")
    if not square_id:
        raise ValueError("square payment id is required")
    amount_cents, currency = _amount_from_payment(payment)
    status = str(payment.get("status") or "UNKNOWN")
    created = str(
        payment.get("created_at")
        or payment.get("updated_at")
        or _utc_now()
    )
    order_id = str(payment.get("order_id") or "")
    customer_id = str(payment.get("customer_id") or "")
    now = _utc_now()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM billing_transactions WHERE square_payment_id = ?",
            (square_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE billing_transactions
                SET status = ?, amount_cents = ?, currency = ?, square_order_id = ?,
                    square_customer_id = ?, occurred_at = ?, raw_json = ?, updated_at = ?
                WHERE square_payment_id = ?
                """,
                (
                    status,
                    amount_cents,
                    currency,
                    order_id or None,
                    customer_id or None,
                    created,
                    json.dumps(payment, ensure_ascii=False, default=str),
                    now,
                    square_id,
                ),
            )
            row_id = existing["id"]
        else:
            row_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO billing_transactions (
                    id, account_id, kind, square_payment_id, square_order_id,
                    square_customer_id, status, amount_cents, currency,
                    occurred_at, raw_json, created_at, updated_at
                ) VALUES (?, ?, 'payment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    account_id,
                    square_id,
                    order_id or None,
                    customer_id or None,
                    status,
                    amount_cents,
                    currency,
                    created,
                    json.dumps(payment, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
        conn.commit()
    return get_transaction(account_id, row_id) or {}


def upsert_square_refund(account_id: str, refund: dict[str, Any]) -> dict[str, Any]:
    square_id = str(refund.get("id") or "")
    if not square_id:
        raise ValueError("square refund id is required")
    money = refund.get("amount_money") or {}
    amount_cents = int(money.get("amount") or 0) if isinstance(money, dict) else 0
    currency = str(money.get("currency") or "USD") if isinstance(money, dict) else "USD"
    status = str(refund.get("status") or "UNKNOWN")
    created = str(refund.get("created_at") or refund.get("updated_at") or _utc_now())
    payment_id = str(refund.get("payment_id") or "")
    now = _utc_now()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM billing_transactions WHERE square_payment_id = ?",
            (square_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE billing_transactions
                SET status = ?, amount_cents = ?, currency = ?, occurred_at = ?,
                    raw_json = ?, updated_at = ?
                WHERE square_payment_id = ?
                """,
                (
                    status,
                    -abs(amount_cents),
                    currency,
                    created,
                    json.dumps(refund, ensure_ascii=False, default=str),
                    now,
                    square_id,
                ),
            )
            row_id = existing["id"]
        else:
            row_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO billing_transactions (
                    id, account_id, kind, square_payment_id, square_order_id,
                    square_customer_id, status, amount_cents, currency,
                    occurred_at, raw_json, created_at, updated_at
                ) VALUES (?, ?, 'refund', ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    account_id,
                    square_id,
                    payment_id or None,
                    status,
                    -abs(amount_cents),
                    currency,
                    created,
                    json.dumps(refund, ensure_ascii=False, default=str),
                    now,
                    now,
                ),
            )
        conn.commit()
    return get_transaction(account_id, row_id) or {}


def get_transaction(account_id: str, transaction_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, kind, square_payment_id, square_order_id,
                   square_customer_id, status, amount_cents, currency,
                   occurred_at, created_at, updated_at
            FROM billing_transactions
            WHERE account_id = ? AND id = ?
            """,
            (account_id, transaction_id),
        ).fetchone()
    return _row_to_tx(row) if row else None


def list_transactions(account_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, account_id, kind, square_payment_id, square_order_id,
                   square_customer_id, status, amount_cents, currency,
                   occurred_at, created_at, updated_at
            FROM billing_transactions
            WHERE account_id = ?
            ORDER BY occurred_at DESC, created_at DESC
            LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
    return [_row_to_tx(row) for row in rows]


def find_account_by_square_payment_id(square_payment_id: str) -> str | None:
    if not square_payment_id:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT account_id FROM billing_transactions
            WHERE square_payment_id = ? OR square_order_id = ?
            LIMIT 1
            """,
            (square_payment_id, square_payment_id),
        ).fetchone()
    return row["account_id"] if row else None


def find_account_for_payment(payment: dict[str, Any]) -> str | None:
    customer_id = str(payment.get("customer_id") or "")
    if customer_id:
        found = subscription_store.find_account_by_square_customer(customer_id)
        if found:
            return found
    note = str(payment.get("note") or "")
    if "account_id=" in note:
        fragment = note.split("account_id=", 1)[1]
        account_id = fragment.split(";", 1)[0].split(",", 1)[0].strip()
        if account_id:
            return account_id
    return None


def _row_to_tx(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "kind": row["kind"],
        "square_payment_id": row["square_payment_id"],
        "square_order_id": row["square_order_id"],
        "square_customer_id": row["square_customer_id"],
        "status": row["status"],
        "amount_cents": int(row["amount_cents"]),
        "currency": row["currency"],
        "occurred_at": row["occurred_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
