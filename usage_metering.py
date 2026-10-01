"""Billable run consumption (plan quota first, then top-up credits)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import subscription_plans
import subscription_store
from app_db import connect

_MIN_REMAINING = 0.001


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def ensure_free_tier_period(account_id: str) -> None:
    """Initialize or roll the 30-day window for accounts without a paid plan."""
    if subscription_store.is_subscription_active(account_id):
        return
    subscription_store.ensure_row(account_id)
    sub = subscription_store.get_subscription(account_id)
    quota = subscription_plans.free_tier_monthly_runs()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    end = _parse_dt(sub["current_period_end"])
    needs_reset = end is None or end <= now
    ts = _utc_now()
    with connect() as conn:
        if needs_reset:
            new_end = now + timedelta(days=30)
            conn.execute(
                """
                UPDATE account_subscriptions
                SET
                    monthly_quota = ?,
                    plan_runs_consumed = 0,
                    current_period_start = ?,
                    current_period_end = ?,
                    updated_at = ?
                WHERE account_id = ?
                  AND status NOT IN ('active', 'past_due')
                """,
                (quota, now.isoformat(), new_end.isoformat(), ts, account_id),
            )
        elif int(sub["monthly_quota"] or 0) != quota:
            conn.execute(
                """
                UPDATE account_subscriptions
                SET monthly_quota = ?, updated_at = ?
                WHERE account_id = ?
                  AND status NOT IN ('active', 'past_due')
                """,
                (quota, ts, account_id),
            )
        conn.commit()


def maybe_reset_billing_period(account_id: str) -> bool:
    """Reset plan usage when the current period has ended. Returns True if reset."""
    ensure_free_tier_period(account_id)
    sub = subscription_store.get_subscription(account_id)
    if not subscription_store.is_subscription_active(account_id):
        return False
    end = _parse_dt(sub["current_period_end"])
    if not end:
        return False
    now = datetime.now(timezone.utc)
    if end > now:
        return False

    new_start = now.replace(microsecond=0)
    new_end = new_start + timedelta(days=30)
    with connect() as conn:
        conn.execute(
            """
            UPDATE account_subscriptions
            SET
                plan_runs_consumed = 0,
                current_period_start = ?,
                current_period_end = ?,
                updated_at = ?
            WHERE account_id = ?
            """,
            (
                new_start.isoformat(),
                new_end.isoformat(),
                _utc_now(),
                account_id,
            ),
        )
        conn.commit()
    return True


def usage_snapshot(account_id: str) -> dict[str, Any]:
    subscription_store.ensure_row(account_id)
    maybe_reset_billing_period(account_id)
    sub = subscription_store.get_subscription(account_id)
    active = subscription_store.is_subscription_active(account_id)
    consumed = float(sub.get("plan_runs_consumed") or 0.0)
    top_up = float(sub["top_up_balance_runs"])
    if active:
        quota = float(sub["monthly_quota"])
        plan_remaining = max(0.0, quota - consumed)
        total_remaining = plan_remaining + top_up
    else:
        quota = float(sub["monthly_quota"] or subscription_plans.free_tier_monthly_runs())
        plan_remaining = max(0.0, quota - consumed)
        total_remaining = plan_remaining

    return {
        "subscription_active": active,
        "free_tier": not active,
        "usage_quota": int(quota) if quota else 0,
        "plan_runs_consumed": round(consumed, 2),
        "usage_used": round(consumed, 2),
        "plan_remaining": round(plan_remaining, 2),
        "top_up_balance": round(top_up, 2) if active else 0.0,
        "total_remaining": round(total_remaining, 2),
        "can_run": total_remaining > _MIN_REMAINING,
        "period_end": sub.get("current_period_end"),
    }


def assert_quota_for_run(account_id: str) -> None:
    from run_limits import RunLimitError

    snap = usage_snapshot(account_id)
    if snap["can_run"]:
        return
    if snap["subscription_active"]:
        raise RunLimitError(
            code="quota_exhausted",
            message=(
                "Monthly plan and top-up credits are used up. "
                "Purchase a top-up or wait for the next billing period."
            ),
        )
    quota = snap["usage_quota"]
    raise RunLimitError(
        code="free_tier_exhausted",
        message=(
            f"Free tier limit reached ({quota} runs per month). "
            "Subscribe to a plan for more agent runs."
        ),
    )


def meter_completed_run(account_id: str, run_id: str) -> dict[str, Any] | None:
    """Apply run_units to subscription ledger once per completed run."""
    maybe_reset_billing_period(account_id)
    active = subscription_store.is_subscription_active(account_id)
    if not active and subscription_plans.free_tier_monthly_runs() <= 0:
        return None
    now = _utc_now()

    with connect() as conn:
        row = conn.execute(
            """
            SELECT status, run_units, usage_metered_at
            FROM agent_runs
            WHERE account_id = ? AND id = ?
            """,
            (account_id, run_id),
        ).fetchone()
        if not row or row["usage_metered_at"]:
            return None
        if row["status"] != "completed":
            return None
        units = float(row["run_units"] or 0.0)
        if not active:
            units = 1.0
        if units <= 0:
            conn.execute(
                """
                UPDATE agent_runs SET usage_metered_at = ? WHERE account_id = ? AND id = ?
                """,
                (now, account_id, run_id),
            )
            conn.commit()
            return usage_snapshot(account_id)

        sub = conn.execute(
            """
            SELECT monthly_quota, plan_runs_consumed, top_up_balance_runs
            FROM account_subscriptions
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchone()
        if not sub:
            return None

        quota = float(sub["monthly_quota"])
        consumed = float(sub["plan_runs_consumed"] or 0.0)
        top_up = float(sub["top_up_balance_runs"]) if active else 0.0
        plan_room = max(0.0, quota - consumed)
        to_plan = min(units, plan_room)
        to_top_up = (units - to_plan) if active else 0.0
        new_consumed = consumed + to_plan
        new_top_up = max(0.0, top_up - to_top_up)

        cur = conn.execute(
            """
            UPDATE agent_runs
            SET usage_metered_at = ?
            WHERE account_id = ? AND id = ? AND usage_metered_at IS NULL
            """,
            (now, account_id, run_id),
        )
        if cur.rowcount == 0:
            conn.commit()
            return None

        conn.execute(
            """
            UPDATE account_subscriptions
            SET plan_runs_consumed = ?, top_up_balance_runs = ?, updated_at = ?
            WHERE account_id = ?
            """,
            (new_consumed, new_top_up, now, account_id),
        )
        conn.commit()

    return usage_snapshot(account_id)


def add_top_up_runs(account_id: str, runs: float) -> dict[str, Any]:
    if runs <= 0:
        raise ValueError("runs must be positive")
    subscription_store.ensure_row(account_id)
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE account_subscriptions
            SET top_up_balance_runs = top_up_balance_runs + ?, updated_at = ?
            WHERE account_id = ?
            """,
            (runs, now, account_id),
        )
        conn.commit()
    return usage_snapshot(account_id)
