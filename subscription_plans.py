"""Product subscription tiers (MultiWorkAgent billing via Square)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SubscriptionPlan:
    tier: str
    display_name: str
    price_usd_cents: int
    monthly_quota: int
    variation_id_env: str
    checkout_url_env: str


PLANS: dict[str, SubscriptionPlan] = {
    "starter": SubscriptionPlan(
        tier="starter",
        display_name="Starter",
        price_usd_cents=1900,
        monthly_quota=50,
        variation_id_env="SQUARE_STARTER_PLAN_VARIATION_ID",
        checkout_url_env="SQUARE_CHECKOUT_URL_STARTER",
    ),
    "pro": SubscriptionPlan(
        tier="pro",
        display_name="Pro",
        price_usd_cents=4900,
        monthly_quota=200,
        variation_id_env="SQUARE_PRO_PLAN_VARIATION_ID",
        checkout_url_env="SQUARE_CHECKOUT_URL_PRO",
    ),
}


def free_tier_monthly_runs() -> int:
    raw = os.environ.get("FREE_TIER_MONTHLY_RUNS", "5").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 5


def get_plan(tier: str) -> SubscriptionPlan | None:
    return PLANS.get(tier.strip().lower())


def plan_variation_id(tier: str) -> str | None:
    plan = get_plan(tier)
    if not plan:
        return None
    raw = os.environ.get(plan.variation_id_env, "").strip()
    return raw or None


def plan_checkout_url(tier: str) -> str | None:
    plan = get_plan(tier)
    if not plan:
        return None
    raw = os.environ.get(plan.checkout_url_env, "").strip()
    return raw or None


def tier_for_variation_id(variation_id: str) -> str | None:
    vid = variation_id.strip()
    if not vid:
        return None
    for tier, plan in PLANS.items():
        env_val = os.environ.get(plan.variation_id_env, "").strip()
        if env_val and env_val == vid:
            return tier
    return None


def plans_for_api() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for plan in PLANS.values():
        items.append(
            {
                "tier": plan.tier,
                "display_name": plan.display_name,
                "price_usd_cents": plan.price_usd_cents,
                "monthly_quota": plan.monthly_quota,
                "square_variation_configured": bool(plan_variation_id(plan.tier)),
                "square_checkout_url_configured": bool(plan_checkout_url(plan.tier)),
            }
        )
    return items
