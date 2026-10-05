"""Square billing invoices cached per account."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import subscription_plans
from app_db import connect, init_app_database


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _format_display_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return iso[:10] if len(iso) >= 10 else iso


def _format_amount(amount_cents: int, currency: str) -> str:
    symbol = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    return f"{symbol}{amount_cents / 100:,.2f}"


def _row_to_invoice(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "square_invoice_id": row["square_invoice_id"],
        "invoice_number": row["invoice_number"],
        "status": row["status"],
        "amount_cents": int(row["amount_cents"]),
        "currency": row["currency"],
        "invoice_date": row["invoice_date"],
        "pdf_url": row["pdf_url"],
        "public_url": row["public_url"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def find_account_by_square_invoice_id(square_invoice_id: str) -> str | None:
    if not square_invoice_id:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT account_id FROM billing_invoices WHERE square_invoice_id = ?",
            (square_invoice_id,),
        ).fetchone()
    return row["account_id"] if row else None


def list_invoices(account_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id, account_id, square_invoice_id, invoice_number, status,
                amount_cents, currency, invoice_date, pdf_url, public_url,
                description, created_at, updated_at
            FROM billing_invoices
            WHERE account_id = ?
            ORDER BY invoice_date DESC, created_at DESC
            LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
    return [_row_to_invoice(row) for row in rows]


def list_for_display(account_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    display: list[dict[str, Any]] = []
    for row in list_invoices(account_id, limit=limit):
        link = row["pdf_url"] or row["public_url"]
        display.append(
            {
                "id": row["id"],
                "date": _format_display_date(row["invoice_date"]),
                "amount": _format_amount(row["amount_cents"], row["currency"]),
                "status": row["status"],
                "invoice_number": row["invoice_number"],
                "pdf_url": link,
                "description": row["description"],
            }
        )
    return display


def upsert_square_invoice(account_id: str, invoice: dict[str, Any]) -> dict[str, Any]:
    square_id = str(invoice.get("id") or "")
    if not square_id:
        raise ValueError("square invoice id is required")

    amount_cents, currency = _extract_amount(invoice)
    invoice_date = (
        invoice.get("updated_at")
        or invoice.get("created_at")
        or invoice.get("scheduled_at")
        or _utc_now()
    )
    public_url = str(invoice.get("public_url") or "")
    pdf_url = str(invoice.get("pdf_url") or public_url or "")
    number = str(invoice.get("invoice_number") or invoice.get("title") or square_id[:8])
    status = str(invoice.get("status") or "UNKNOWN")
    description = str(invoice.get("title") or invoice.get("description") or "Square invoice")

    now = _utc_now()
    record_id = str(uuid.uuid4())
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM billing_invoices WHERE square_invoice_id = ?
            """,
            (square_id,),
        ).fetchone()
        if existing:
            record_id = existing["id"]
            conn.execute(
                """
                UPDATE billing_invoices
                SET
                    invoice_number = ?,
                    status = ?,
                    amount_cents = ?,
                    currency = ?,
                    invoice_date = ?,
                    pdf_url = ?,
                    public_url = ?,
                    description = ?,
                    updated_at = ?
                WHERE square_invoice_id = ?
                """,
                (
                    number,
                    status,
                    amount_cents,
                    currency,
                    invoice_date,
                    pdf_url or None,
                    public_url or None,
                    description,
                    now,
                    square_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO billing_invoices (
                    id, account_id, square_invoice_id, invoice_number, status,
                    amount_cents, currency, invoice_date, pdf_url, public_url,
                    description, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    account_id,
                    square_id,
                    number,
                    status,
                    amount_cents,
                    currency,
                    invoice_date,
                    pdf_url or None,
                    public_url or None,
                    description,
                    now,
                    now,
                ),
            )
        conn.commit()

    rows = list_invoices(account_id, limit=100)
    for row in rows:
        if row["square_invoice_id"] == square_id:
            return row
    raise RuntimeError("failed to upsert invoice")


def _extract_amount(invoice: dict[str, Any]) -> tuple[int, str]:
    currency = "USD"
    candidates: list[dict[str, Any]] = []
    for req in invoice.get("payment_requests") or []:
        if not isinstance(req, dict):
            continue
        for money_key in (
            "total_completed_amount_money",
            "computed_amount_money",
            "requested_amount_money",
        ):
            money = req.get(money_key)
            if isinstance(money, dict) and money.get("amount") is not None:
                candidates.append(money)

    if not candidates:
        return 0, currency

    money = candidates[0]
    return int(money.get("amount") or 0), str(money.get("currency") or currency)


def create_mock_subscription_invoice(
    account_id: str,
    plan_tier: str,
    *,
    billing_interval: str = "monthly",
) -> dict[str, Any]:
    plan = subscription_plans.get_plan(plan_tier)
    if not plan:
        raise ValueError("unknown plan tier")
    interval = subscription_plans.normalize_billing_interval(billing_interval)
    amount = subscription_plans.checkout_price_cents(plan_tier, interval)
    interval_label = subscription_plans.billing_interval_label(interval)
    now = _utc_now()
    square_id = f"mock-invoice-{uuid.uuid4()}"
    payload = {
        "id": square_id,
        "invoice_number": f"MOCK-{plan.tier.upper()}-{now[:10]}",
        "status": "PAID",
        "title": f"{plan.display_name} subscription ({interval_label})",
        "created_at": now,
        "updated_at": now,
        "public_url": "",
        "payment_requests": [
            {
                "computed_amount_money": {
                    "amount": amount,
                    "currency": "USD",
                }
            }
        ],
    }
    return upsert_square_invoice(account_id, payload)


def invoice_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "square_invoice_id": row["square_invoice_id"],
        "invoice_number": row["invoice_number"],
        "status": row["status"],
        "amount_cents": row["amount_cents"],
        "currency": row["currency"],
        "amount": _format_amount(row["amount_cents"], row["currency"]),
        "invoice_date": row["invoice_date"],
        "date": _format_display_date(row["invoice_date"]),
        "pdf_url": row["pdf_url"] or row["public_url"],
        "description": row["description"],
    }
