"""Account-wide execution limits (concurrency and daily breaker)."""

from __future__ import annotations

import os
from typing import Any

import run_store
import usage_metering


def concurrent_max() -> int:
    raw = os.environ.get("AGENT_CONCURRENT_MAX", "2")
    try:
        return max(1, int(raw))
    except ValueError:
        return 2


def daily_max() -> int:
    raw = os.environ.get("AGENT_DAILY_RUN_LIMIT", "")
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return run_store.RUNS_DAILY_LIMIT


class RunLimitError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message}


def limits_snapshot(account_id: str) -> dict[str, Any]:
    run_store.release_stale_running_runs(account_id)
    running = run_store.count_running_runs(account_id)
    used_24h = run_store.count_runs_last_24h(account_id)
    cmax = concurrent_max()
    dmax = daily_max()
    usage = usage_metering.usage_snapshot(account_id)
    blocked_code = None
    blocked_message = None
    if running >= cmax:
        blocked_code = "concurrent_limit"
        blocked_message = (
            f"{cmax} runs are already in progress for this account. "
            "Wait for one to finish before starting another."
        )
    elif usage.get("subscription_active") and used_24h >= dmax:
        blocked_code = "daily_limit"
        blocked_message = (
            f"Daily limit reached ({dmax} runs in 24 hours). "
            "New runs are paused until older runs fall outside the window."
        )
    if blocked_code is None and not usage["can_run"]:
        if usage["subscription_active"]:
            blocked_code = "quota_exhausted"
            blocked_message = (
                "Monthly plan and top-up credits are used up. "
                "Purchase a top-up or wait for the next billing period."
            )
        else:
            quota = usage["usage_quota"]
            blocked_code = "free_tier_exhausted"
            blocked_message = (
                f"Free tier limit reached ({quota} runs per month). "
                "Subscribe to a plan for more agent runs."
            )

    if usage.get("free_tier"):
        runs_display_used = int(float(usage.get("usage_used") or 0))
        runs_display_max = int(usage.get("usage_quota") or 0)
        runs_display_period = "month"
    else:
        runs_display_used = used_24h
        runs_display_max = dmax
        runs_display_period = "day"

    return {
        "concurrent": running,
        "concurrent_max": cmax,
        "runs_24h": used_24h,
        "runs_daily_max": dmax,
        "runs_display_used": runs_display_used,
        "runs_display_max": runs_display_max,
        "runs_display_period": runs_display_period,
        "usage": usage,
        "can_run": blocked_code is None,
        "blocked_code": blocked_code,
        "blocked_message": blocked_message,
    }


def assert_can_start(account_id: str) -> None:
    snap = limits_snapshot(account_id)
    if snap["can_run"]:
        return
    raise RunLimitError(
        code=snap["blocked_code"] or "limit",
        message=snap["blocked_message"] or "Run limit reached.",
    )
