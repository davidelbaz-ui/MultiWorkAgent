"""Non-secret production readiness (agent, Square billing) for /health and admin."""

from __future__ import annotations

import os
from typing import Any

import subscription_plans


def agent_status() -> dict[str, Any]:
    import agent_executor

    provider = agent_executor.agent_provider_name()
    mock = agent_executor.agent_mock_enabled()
    ready = agent_executor.agent_api_ready()
    return {
        "provider": provider,
        "mock": mock,
        "ready": ready,
        "model": agent_executor.agent_model_name() if ready or mock else None,
    }


def square_status() -> dict[str, Any]:
    import square_billing
    from app_urls import square_webhook_notification_url

    token = bool(os.environ.get("SQUARE_ACCESS_TOKEN", "").strip())
    location = bool(os.environ.get("SQUARE_LOCATION_ID", "").strip())
    webhook_key = bool(os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "").strip())
    missing_plans: list[str] = []
    for tier in subscription_plans.PLAN_TIER_ORDER:
        for interval in subscription_plans.BILLING_INTERVALS:
            if not subscription_plans.plan_variation_id(
                tier, interval
            ) and not subscription_plans.plan_checkout_url(tier, interval):
                missing_plans.append(f"{tier}_{interval}")
    return {
        "mode": square_billing.billing_mode(),
        "access_token_set": token,
        "location_set": location,
        "webhook_signature_key_set": webhook_key,
        "webhook_notification_url": square_webhook_notification_url(),
        "plans_missing_variation_or_checkout_url": missing_plans,
    }


def public_deployment_status() -> dict[str, Any]:
    return {
        "agent": agent_status(),
        "billing": square_status(),
    }
