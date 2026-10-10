"""Assemble admin user / account profile and unified activity timeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import account_activity_store
import auth_store
import billing_transaction_store
import business_store
import connection_store
import database_store
import invoice_store
import run_store
import subscription_plans
import subscription_store
import support_store
from app_db import connect


def _format_ts(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    except ValueError:
        return iso


def plan_display(sub: dict[str, Any]) -> str:
    tier = (sub.get("plan_tier") or "none").lower()
    status = (sub.get("status") or "inactive").lower()
    if tier in ("none", "") or status in ("inactive", "canceled"):
        return "Free"
    plan = subscription_plans.get_plan(tier)
    label = plan.display_name if plan else tier.capitalize()
    interval = subscription_plans.billing_interval_label(
        sub.get("billing_interval") or "monthly"
    )
    suffix = f" · {interval}"
    if status == "past_due":
        return f"{label}{suffix} (past due)"
    if status == "pending":
        return f"{label}{suffix} (pending)"
    return f"{label}{suffix}"


def _timeline_item(
    *,
    at: str,
    category: str,
    title: str,
    detail: str | None = None,
    source: str,
    source_id: str | None = None,
) -> dict[str, Any]:
    return {
        "at": at,
        "at_display": _format_ts(at),
        "category": category,
        "title": title,
        "detail": detail or "",
        "source": source,
        "source_id": source_id,
    }


def build_timeline(account_id: str, *, limit: int = 400) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for row in account_activity_store.list_for_account(account_id, limit=limit):
        extra = ""
        if row.get("detail"):
            extra = str(row["detail"].get("message") or row["detail"].get("status") or "")
        events.append(
            _timeline_item(
                at=row["created_at"],
                category=row["category"],
                title=row["summary"],
                detail=extra or f"{row['action']}",
                source="activity_log",
                source_id=row["id"],
            )
        )

    for run in run_store.list_runs_for_account(account_id, limit=150):
        title = f"Agent run · {run.get('status') or 'unknown'}"
        summary = run.get("summary") or run.get("id", "")
        detail = (
            f"Tokens in/out: {run.get('input_tokens', 0)}/{run.get('output_tokens', 0)}"
            f" · units {run.get('run_units', 0)}"
        )
        if run.get("error_code"):
            detail += f" · {run['error_code']}"
        events.append(
            _timeline_item(
                at=run.get("completed_at") or run.get("created_at") or "",
                category="agent",
                title=title,
                detail=f"{summary} — {detail}",
                source="agent_run",
                source_id=run.get("id"),
            )
        )

    for inv in invoice_store.list_invoices(account_id, limit=80):
        amt = subscription_plans.format_usd(int(inv.get("amount_cents") or 0))
        events.append(
            _timeline_item(
                at=inv.get("invoice_date") or inv.get("created_at") or "",
                category="billing",
                title=f"Invoice {inv.get('invoice_number') or inv.get('square_invoice_id', '')[:8]}",
                detail=f"{inv.get('status')} · {amt} · {inv.get('description') or ''}",
                source="invoice",
                source_id=inv.get("id"),
            )
        )

    for tx in billing_transaction_store.list_transactions(account_id, limit=80):
        amt = subscription_plans.format_usd(abs(int(tx.get("amount_cents") or 0)))
        sign = "-" if int(tx.get("amount_cents") or 0) < 0 else ""
        events.append(
            _timeline_item(
                at=tx.get("occurred_at") or tx.get("created_at") or "",
                category="billing",
                title=f"{tx.get('kind', 'payment').capitalize()} · {tx.get('status')}",
                detail=f"{sign}{amt} · Square {tx.get('square_payment_id', '')[:12]}…",
                source="transaction",
                source_id=tx.get("id"),
            )
        )

    for biz in business_store.list_businesses(account_id, include_archived=True):
        events.append(
            _timeline_item(
                at=biz.get("created_at") or "",
                category="business",
                title=f"Business created · {biz.get('name')}",
                detail=biz.get("industry") or "",
                source="business",
                source_id=biz.get("id"),
            )
        )
        if biz.get("archived_at"):
            events.append(
                _timeline_item(
                    at=biz["archived_at"],
                    category="business",
                    title=f"Business archived · {biz.get('name')}",
                    detail="",
                    source="business",
                    source_id=biz.get("id"),
                )
            )

    for conn in connection_store.list_connections(account_id):
        events.append(
            _timeline_item(
                at=conn.get("updated_at") or conn.get("created_at") or "",
                category="integration",
                title=f"Integration · {conn.get('provider_name')} ({conn.get('status')})",
                detail=conn.get("credential_hint") or conn.get("auth_type", ""),
                source="integration",
                source_id=conn.get("id"),
            )
        )

    for db in database_store.list_connections(account_id):
        events.append(
            _timeline_item(
                at=db.get("updated_at") or db.get("created_at") or "",
                category="database",
                title=f"Database · {db.get('name')} ({db.get('status')})",
                detail=f"{db.get('engine')} · {db.get('access_mode')}",
                source="database",
                source_id=db.get("id"),
            )
        )

    for msg in support_store.list_messages(account_id):
        role = msg.get("sender_type") or msg.get("sender_role") or "user"
        preview = (msg.get("body") or "")[:200]
        events.append(
            _timeline_item(
                at=msg.get("created_at") or "",
                category="support",
                title=f"Support message · {role}",
                detail=preview,
                source="support",
                source_id=str(msg.get("id")),
            )
        )

    events = [e for e in events if e.get("at")]
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def build_user_profile(user_id: str) -> dict[str, Any] | None:
    user = auth_store.get_user(user_id)
    if not user:
        return None
    membership = auth_store.get_primary_membership(user_id)
    if not membership:
        return None
    account_id = membership["account_id"]
    sub = subscription_store.get_subscription(account_id)
    team = auth_store.list_account_members(account_id)
    account_created_at = None
    with connect() as conn:
        acc_row = conn.execute(
            "SELECT created_at FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        if acc_row:
            account_created_at = acc_row["created_at"]

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user.get("display_name") or "",
            "name": user.get("name") or user["email"],
            "created_at": user.get("created_at"),
            "created_at_display": _format_ts(user.get("created_at")),
            "last_login_at": user.get("last_login_at"),
            "last_login_display": _format_ts(user.get("last_login_at")),
            "role": membership.get("role"),
            "role_label": auth_store.ROLE_LABELS.get(membership.get("role"), membership.get("role")),
        },
        "account": {
            "id": account_id,
            "created_at": account_created_at,
            "created_at_display": _format_ts(account_created_at),
        },
        "subscription": {
            "plan_label": plan_display(sub),
            "plan_tier": sub.get("plan_tier"),
            "status": sub.get("status"),
            "billing_interval": sub.get("billing_interval"),
            "monthly_quota": sub.get("monthly_quota"),
            "plan_runs_consumed": sub.get("plan_runs_consumed"),
            "top_up_balance_runs": sub.get("top_up_balance_runs"),
            "current_period_end": sub.get("current_period_end"),
            "square_customer_id": sub.get("square_customer_id"),
            "square_subscription_id": sub.get("square_subscription_id"),
        },
        "invoices": invoice_store.list_invoices(account_id, limit=50),
        "transactions": billing_transaction_store.list_transactions(account_id, limit=50),
        "business_count": len(business_store.list_businesses(account_id)),
        "integration_count": len(connection_store.list_connections(account_id)),
        "database_count": len(database_store.list_connections(account_id)),
        "team": team,
        "timeline": build_timeline(account_id),
    }
