"""Account subscription ledger (plan, quota, billing period — synced from Square)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import business_store
import subscription_plans
from app_db import connect, init_app_database

_ACTIVE_STATUSES = frozenset({"active", "past_due"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_period_end(raw: str | None) -> str | None:
    dt = _parse_dt(raw)
    if not dt:
        return None
    return dt.strftime("%b %d, %Y")


def bootstrap() -> None:
    init_app_database()


def ensure_row(account_id: str) -> None:
    business_store.ensure_account(account_id)
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO account_subscriptions (
                account_id, plan_tier, status, monthly_quota, top_up_balance_runs,
                plan_runs_consumed, current_period_start, current_period_end,
                square_customer_id, square_subscription_id, cancel_at_period_end,
                created_at, updated_at
            ) VALUES (?, 'none', 'inactive', 0, 0, 0, NULL, NULL, NULL, NULL, 0, ?, ?)
            ON CONFLICT(account_id) DO NOTHING
            """,
            (account_id, now, now),
        )
        conn.commit()


def _row_to_sub(row: Any) -> dict[str, Any]:
    return {
        "account_id": row["account_id"],
        "plan_tier": row["plan_tier"],
        "billing_interval": row["billing_interval"] if "billing_interval" in row.keys() else "monthly",
        "status": row["status"],
        "monthly_quota": int(row["monthly_quota"]),
        "top_up_balance_runs": float(row["top_up_balance_runs"]),
        "plan_runs_consumed": float(row["plan_runs_consumed"]),
        "current_period_start": row["current_period_start"],
        "current_period_end": row["current_period_end"],
        "square_customer_id": row["square_customer_id"],
        "square_subscription_id": row["square_subscription_id"],
        "cancel_at_period_end": bool(row["cancel_at_period_end"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_subscription(account_id: str) -> dict[str, Any]:
    ensure_row(account_id)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                account_id, plan_tier, billing_interval, status, monthly_quota, top_up_balance_runs,
                plan_runs_consumed, current_period_start, current_period_end,
                square_customer_id, square_subscription_id, cancel_at_period_end,
                created_at, updated_at
            FROM account_subscriptions
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
    if not row:
        raise RuntimeError("subscription row missing")
    return _row_to_sub(row)


def find_account_by_square_customer(square_customer_id: str) -> str | None:
    if not square_customer_id:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT account_id FROM account_subscriptions
            WHERE square_customer_id = ?
            """,
            (square_customer_id,),
        ).fetchone()
    return row["account_id"] if row else None


def find_account_by_square_subscription(square_subscription_id: str) -> str | None:
    if not square_subscription_id:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT account_id FROM account_subscriptions
            WHERE square_subscription_id = ?
            """,
            (square_subscription_id,),
        ).fetchone()
    return row["account_id"] if row else None


def set_square_customer_id(account_id: str, square_customer_id: str) -> None:
    ensure_row(account_id)
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE account_subscriptions
            SET square_customer_id = ?, updated_at = ?
            WHERE account_id = ?
            """,
            (square_customer_id, now, account_id),
        )
        conn.commit()


def set_pending_checkout(
    account_id: str,
    plan_tier: str,
    *,
    billing_interval: str = "monthly",
) -> dict[str, Any]:
    plan = subscription_plans.get_plan(plan_tier)
    if not plan:
        raise ValueError("unknown plan tier")
    interval = subscription_plans.normalize_billing_interval(billing_interval)
    ensure_row(account_id)
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE account_subscriptions
            SET plan_tier = ?, billing_interval = ?, status = 'pending', monthly_quota = ?, updated_at = ?
            WHERE account_id = ?
            """,
            (plan.tier, interval, plan.monthly_quota, now, account_id),
        )
        conn.commit()
    return get_subscription(account_id)


def activate_plan(
    account_id: str,
    *,
    plan_tier: str,
    status: str = "active",
    billing_interval: str = "monthly",
    period_start: str | None = None,
    period_end: str | None = None,
    square_customer_id: str | None = None,
    square_subscription_id: str | None = None,
    cancel_at_period_end: bool = False,
) -> dict[str, Any]:
    plan = subscription_plans.get_plan(plan_tier)
    if not plan:
        raise ValueError("unknown plan tier")
    interval = subscription_plans.normalize_billing_interval(billing_interval)
    if status not in ("pending", "active", "past_due", "canceled", "inactive"):
        raise ValueError("invalid subscription status")

    ensure_row(account_id)
    now = _utc_now()
    if period_start is None:
        period_start = now
    if period_end is None and status in _ACTIVE_STATUSES:
        end_dt = datetime.now(timezone.utc) + timedelta(days=30)
        period_end = end_dt.replace(microsecond=0).isoformat()

    with connect() as conn:
        conn.execute(
            """
            UPDATE account_subscriptions
            SET
                plan_tier = ?,
                billing_interval = ?,
                status = ?,
                monthly_quota = ?,
                current_period_start = ?,
                current_period_end = ?,
                square_customer_id = COALESCE(?, square_customer_id),
                square_subscription_id = COALESCE(?, square_subscription_id),
                cancel_at_period_end = ?,
                plan_runs_consumed = CASE
                    WHEN ? IN ('active', 'pending') AND status NOT IN ('active', 'past_due')
                    THEN 0
                    ELSE plan_runs_consumed
                END,
                updated_at = ?
            WHERE account_id = ?
            """,
            (
                plan.tier,
                interval,
                status,
                plan.monthly_quota,
                period_start,
                period_end,
                square_customer_id,
                square_subscription_id,
                1 if cancel_at_period_end else 0,
                status,
                now,
                account_id,
            ),
        )
        conn.commit()
    sub = get_subscription(account_id)
    try:
        import account_activity_store

        account_activity_store.record(
            account_id,
            category="billing",
            action="subscription_update",
            summary=f"Subscription · {plan.tier} · {status}",
            detail={
                "plan_tier": plan.tier,
                "status": status,
                "billing_interval": interval,
            },
        )
    except Exception:
        pass
    return sub


def cancel_at_period_end(account_id: str) -> dict[str, Any]:
    sub = get_subscription(account_id)
    if sub["status"] not in _ACTIVE_STATUSES:
        raise ValueError("no active subscription to cancel")
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE account_subscriptions
            SET cancel_at_period_end = 1, updated_at = ?
            WHERE account_id = ?
            """,
            (now, account_id),
        )
        conn.commit()
    return get_subscription(account_id)


def is_subscription_active(account_id: str) -> bool:
    sub = get_subscription(account_id)
    return sub["status"] in _ACTIVE_STATUSES and sub["plan_tier"] in subscription_plans.PLANS


def billing_summary(account_id: str) -> dict[str, Any]:
    import usage_metering

    sub = get_subscription(account_id)
    usage = usage_metering.usage_snapshot(account_id)
    plan_def = subscription_plans.get_plan(sub["plan_tier"])
    display_plan = plan_def.display_name if plan_def and sub["status"] in _ACTIVE_STATUSES | {"pending"} else None
    if display_plan and sub.get("billing_interval") == "annual":
        display_plan = f"{display_plan} (Annual)"
    if sub["status"] == "canceled" or sub["plan_tier"] == "none":
        display_plan = None

    if usage.get("free_tier"):
        display_plan = "Free"
        quota = usage["usage_quota"]
    elif display_plan:
        quota = usage["usage_quota"]
    else:
        quota = 0
    return {
        "plan": display_plan,
        "plan_tier": sub["plan_tier"],
        "billing_interval": sub.get("billing_interval") or "monthly",
        "status": sub["status"],
        "usage_quota": quota,
        "usage_used": usage["usage_used"],
        "top_up_balance": usage["top_up_balance"],
        "billing_period_end": _format_period_end(sub["current_period_end"]),
        "current_period_end": sub["current_period_end"],
        "cancel_at_period_end": sub["cancel_at_period_end"],
        "square_customer_id": sub["square_customer_id"],
        "square_subscription_id": sub["square_subscription_id"],
    }


def subscription_to_api(account_id: str) -> dict[str, Any]:
    import usage_metering

    sub = get_subscription(account_id)
    summary = billing_summary(account_id)
    usage = usage_metering.usage_snapshot(account_id)
    return {
        **summary,
        **usage,
        "monthly_quota": sub["monthly_quota"],
        "is_active": is_subscription_active(account_id),
        "plans": subscription_plans.plans_for_api(),
    }


def record_webhook_event(
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    account_id: str | None = None,
) -> bool:
    """Insert event if new. Returns False if duplicate."""
    now = _utc_now()
    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM square_webhook_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO square_webhook_events (
                event_id, event_type, payload_json, account_id, received_at, processed_at
            ) VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (event_id, event_type, json.dumps(payload, ensure_ascii=False), account_id, now),
        )
        conn.commit()
    return True


def mark_webhook_processed(event_id: str, account_id: str | None = None) -> None:
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE square_webhook_events
            SET processed_at = ?, account_id = COALESCE(?, account_id)
            WHERE event_id = ?
            """,
            (now, account_id, event_id),
        )
        conn.commit()
