"""Emit notifications for agent runs, quota, limits, and billing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import notification_store
import subscription_store
import usage_metering


def _agent_href(thread_id: str | None) -> str:
    if thread_id:
        return f"/agent?thread={thread_id}"
    return "/agent"


def notify_run_finished(account_id: str, run: dict[str, Any]) -> None:
    status = run.get("status")
    thread_id = run.get("thread_id")
    summary = run.get("summary") or "Agent run"
    href = _agent_href(thread_id)

    if status == "completed":
        units = run.get("run_units")
        detail = f" ({units} run units)" if units else ""
        notification_store.create_notification(
            account_id,
            kind="run_completed",
            title="Run completed",
            body=f"{summary}{detail}",
            href=href,
        )
        return

    if status in ("error", "timeout", "unconfigured"):
        code = run.get("error_code") or status
        notification_store.create_notification(
            account_id,
            kind="run_failed",
            title="Run failed",
            body=f"{summary} — {code}",
            href=href,
        )


def notify_run_blocked(account_id: str, *, error_code: str, summary: str) -> None:
    if error_code == "daily_limit":
        notification_store.create_notification(
            account_id,
            kind="daily_limit",
            title="Daily run limit reached",
            body="New agent runs are paused until older runs fall outside the 24-hour window.",
            href="/billing",
            dedupe_key=f"daily_limit:{account_id}:{datetime.now(timezone.utc).date().isoformat()}",
        )
        return

    if error_code == "quota_exhausted":
        notification_store.create_notification(
            account_id,
            kind="quota_100",
            title="Plan quota exhausted",
            body="Monthly plan and top-up credits are used up. Upgrade or add a top-up to continue.",
            href="/billing",
            dedupe_key=_quota_dedupe_key(account_id, "100"),
        )


def _quota_dedupe_key(account_id: str, suffix: str) -> str:
    sub = subscription_store.get_subscription(account_id)
    period = sub.get("current_period_end") or "none"
    return f"quota_{suffix}:{account_id}:{period}"


def notify_after_usage_metered(account_id: str) -> None:
    if not subscription_store.is_subscription_active(account_id):
        return
    snap = usage_metering.usage_snapshot(account_id)
    quota = snap.get("usage_quota") or 0
    if quota <= 0:
        return
    used = float(snap.get("usage_used") or 0)
    ratio = used / quota
    if ratio >= 1.0:
        notification_store.create_notification(
            account_id,
            kind="quota_100",
            title="Quota at 100%",
            body=f"You have used {used:g} of {quota} plan runs this period.",
            href="/billing",
            dedupe_key=_quota_dedupe_key(account_id, "100"),
        )
    elif ratio >= 0.8:
        notification_store.create_notification(
            account_id,
            kind="quota_80",
            title="Quota at 80%",
            body=f"You have used {used:g} of {quota} plan runs this period.",
            href="/billing",
            dedupe_key=_quota_dedupe_key(account_id, "80"),
        )


def notify_payment_issue(account_id: str, *, title: str, body: str) -> None:
    notification_store.create_notification(
        account_id,
        kind="payment_issue",
        title=title,
        body=body,
        href="/billing",
        dedupe_key=f"payment:{account_id}:{title}",
    )
