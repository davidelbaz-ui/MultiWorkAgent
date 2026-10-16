"""Non-secret production readiness (agent, Stripe billing) for /health and admin."""

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


def stripe_status() -> dict[str, Any]:
    import stripe_billing
    from app_urls import stripe_webhook_notification_url

    secret = bool(os.environ.get("STRIPE_SECRET_KEY", "").strip())
    webhook_secret = bool(os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip())
    missing_plans: list[str] = []
    for tier in subscription_plans.PLAN_TIER_ORDER:
        for interval in subscription_plans.BILLING_INTERVALS:
            if not subscription_plans.stripe_price_id(
                tier, interval
            ) and not subscription_plans.plan_checkout_url(tier, interval):
                missing_plans.append(f"{tier}_{interval}")
    return {
        "mode": stripe_billing.billing_mode(),
        "secret_key_set": secret,
        "webhook_secret_set": webhook_secret,
        "webhook_notification_url": stripe_webhook_notification_url(),
        "plans_missing_price_or_checkout_url": missing_plans,
    }


def public_deployment_status() -> dict[str, Any]:
    return {
        "agent": agent_status(),
        "billing": stripe_status(),
    }
