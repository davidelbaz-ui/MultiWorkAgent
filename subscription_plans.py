"""Product subscription tiers (MultiWorkAgent billing via Square)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

ANNUAL_SAVINGS_PERCENT = 20
BILLING_INTERVALS = ("monthly", "annual")


@dataclass(frozen=True)
class SubscriptionPlan:
    tier: str
    display_name: str
    monthly_price_usd_cents: int
    monthly_quota: int


PLANS: dict[str, SubscriptionPlan] = {
    "starter": SubscriptionPlan(
        tier="starter",
        display_name="Starter",
        monthly_price_usd_cents=4999,
        monthly_quota=150,
    ),
    "pro": SubscriptionPlan(
        tier="pro",
        display_name="Pro",
        monthly_price_usd_cents=14999,
        monthly_quota=500,
    ),
    "enterprise": SubscriptionPlan(
        tier="enterprise",
        display_name="Enterprise",
        monthly_price_usd_cents=24999,
        monthly_quota=1000,
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


def normalize_billing_interval(raw: str | None) -> str:
    value = (raw or "monthly").strip().lower()
    return value if value in BILLING_INTERVALS else "monthly"


def checkout_price_cents(tier: str, billing_interval: str) -> int:
    plan = get_plan(tier)
    if not plan:
        raise ValueError("unknown plan tier")
    interval = normalize_billing_interval(billing_interval)
    if interval == "annual":
        yearly = plan.monthly_price_usd_cents * 12 * (100 - ANNUAL_SAVINGS_PERCENT)
        return int(round(yearly / 100))
    return plan.monthly_price_usd_cents


def format_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _variation_env_key(tier: str, billing_interval: str) -> str:
    interval = normalize_billing_interval(billing_interval)
    upper = tier.strip().upper()
    if interval == "annual":
        return f"SQUARE_{upper}_ANNUAL_PLAN_VARIATION_ID"
    return f"SQUARE_{upper}_PLAN_VARIATION_ID"


def _checkout_url_env_key(tier: str, billing_interval: str) -> str:
    interval = normalize_billing_interval(billing_interval)
    upper = tier.strip().upper()
    if interval == "annual":
        return f"SQUARE_CHECKOUT_URL_{upper}_ANNUAL"
    return f"SQUARE_CHECKOUT_URL_{upper}"


def plan_variation_id(tier: str, billing_interval: str = "monthly") -> str | None:
    if not get_plan(tier):
        return None
    raw = os.environ.get(_variation_env_key(tier, billing_interval), "").strip()
    return raw or None


def plan_checkout_url(tier: str, billing_interval: str = "monthly") -> str | None:
    if not get_plan(tier):
        return None
    raw = os.environ.get(_checkout_url_env_key(tier, billing_interval), "").strip()
    return raw or None


def tier_and_interval_for_variation_id(variation_id: str) -> tuple[str, str] | None:
    vid = variation_id.strip()
    if not vid:
        return None
    for tier in PLANS:
        for interval in BILLING_INTERVALS:
            env_val = plan_variation_id(tier, interval)
            if env_val and env_val == vid:
                return tier, interval
    return None


def parse_plan_from_payment_note(note: str) -> tuple[str | None, str]:
    """Extract plan tier and billing interval from Square payment_note / subscription note."""
    text = str(note)
    tier: str | None = None
    interval = "monthly"
    if "plan=starter" in text:
        tier = "starter"
    elif "plan=pro" in text:
        tier = "pro"
    elif "plan=enterprise" in text:
        tier = "enterprise"
    if "interval=annual" in text:
        interval = "annual"
    return tier, interval


def is_valid_checkout(plan_tier: str, billing_interval: str) -> bool:
    return get_plan(plan_tier) is not None and normalize_billing_interval(billing_interval) in BILLING_INTERVALS


def billing_interval_label(interval: str) -> str:
    return "Annual" if normalize_billing_interval(interval) == "annual" else "Monthly"


def catalog_for_billing() -> list[dict[str, Any]]:
    """Pricing cards for the Billing page."""
    items: list[dict[str, Any]] = []
    for plan in PLANS.values():
        annual_cents = checkout_price_cents(plan.tier, "annual")
        monthly_equiv = int(round(annual_cents / 12))
        items.append(
            {
                "tier": plan.tier,
                "display_name": plan.display_name,
                "monthly_quota": plan.monthly_quota,
                "monthly_price_cents": plan.monthly_price_usd_cents,
                "monthly_price": format_usd(plan.monthly_price_usd_cents),
                "annual_price_cents": annual_cents,
                "annual_price": format_usd(annual_cents),
                "annual_monthly_equiv": format_usd(monthly_equiv),
                "annual_savings_percent": ANNUAL_SAVINGS_PERCENT,
            }
        )
    return items


def plans_for_api() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for plan in PLANS.values():
        for interval in BILLING_INTERVALS:
            items.append(
                {
                    "tier": plan.tier,
                    "billing_interval": interval,
                    "display_name": plan.display_name,
                    "price_usd_cents": checkout_price_cents(plan.tier, interval),
                    "monthly_quota": plan.monthly_quota,
                    "square_variation_configured": bool(plan_variation_id(plan.tier, interval)),
                    "square_checkout_url_configured": bool(plan_checkout_url(plan.tier, interval)),
                }
            )
    return items


# Backward-compatible alias used in a few places
def tier_for_variation_id(variation_id: str) -> str | None:
    resolved = tier_and_interval_for_variation_id(variation_id)
    return resolved[0] if resolved else None
