"""Stripe subscription checkout + webhook handling."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

import billing_transaction_store
import invoice_store
import subscription_plans
import subscription_store

class StripeBillingError(Exception):
    pass


def is_billing_mock_enabled() -> bool:
    return os.environ.get("STRIPE_MOCK", "").strip() in ("1", "true", "yes") or os.environ.get(
        "BILLING_DEV_MOCK", ""
    ).strip() in ("1", "true", "yes")


def _secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def publishable_key() -> str:
    return os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()


def validate_publishable_key_for_browser(key: str) -> str | None:
    """Return an error message if key is missing or is a secret key."""
    trimmed = (key or "").strip()
    if not trimmed:
        return "STRIPE_PUBLISHABLE_KEY is not set. Required for on-page checkout."
    if trimmed.startswith("sk_"):
        return (
            "STRIPE_PUBLISHABLE_KEY must be your publishable key (pk_live_… or pk_test_…), "
            "not the secret key (sk_…). In Stripe Dashboard → Developers → API keys, copy Publishable key."
        )
    if not trimmed.startswith("pk_"):
        return "STRIPE_PUBLISHABLE_KEY should start with pk_live_ or pk_test_."
    return None


def _checkout_session_payment_params() -> list[tuple[str, str]]:
    """Checkout Session payment methods (not PaymentIntent automatic_payment_methods)."""
    pmc = os.environ.get("STRIPE_PAYMENT_METHOD_CONFIGURATION", "").strip()
    if pmc:
        return [("payment_method_configuration", pmc)]
    # Explicit card: required when Dashboard dynamic methods are empty for subscription Checkout.
    # Apple Pay / Google Pay still appear on hosted Checkout when enabled in Dashboard (wallet UI on card).
    return [("payment_method_types[0]", "card")]


def is_stripe_configured() -> bool:
    if not _secret_key():
        return False
    for tier in subscription_plans.PLAN_TIER_ORDER:
        for interval in subscription_plans.BILLING_INTERVALS:
            if subscription_plans.stripe_price_id(tier, interval) or subscription_plans.plan_checkout_url(
                tier, interval
            ):
                return True
    return False


def billing_mode() -> str:
    if is_stripe_configured():
        return "stripe"
    if is_billing_mock_enabled():
        return "mock"
    return "unconfigured"


def _stripe_request(
    method: str,
    path: str,
    params: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    secret = _secret_key()
    if not secret:
        raise StripeBillingError("STRIPE_SECRET_KEY is not set")
    url = f"https://api.stripe.com/v1{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if params is not None:
        data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise StripeBillingError(f"Stripe API error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise StripeBillingError(str(exc)) from exc

    parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        raise StripeBillingError("unexpected Stripe response")
    if parsed.get("error"):
        raise StripeBillingError(json.dumps(parsed["error"], ensure_ascii=False))
    return parsed


def ensure_stripe_customer(account_id: str, *, email: str | None = None) -> str:
    sub = subscription_store.get_subscription(account_id)
    if sub["stripe_customer_id"]:
        return sub["stripe_customer_id"]

    params: list[tuple[str, str]] = [
        ("metadata[account_id]", account_id),
    ]
    if email:
        params.append(("email", email.strip()))
    result = _stripe_request("POST", "/customers", params)
    customer_id = result.get("id")
    if not customer_id:
        raise StripeBillingError("Stripe did not return a customer id")
    subscription_store.set_stripe_customer_id(account_id, str(customer_id))
    return str(customer_id)


def create_checkout_session(
    account_id: str,
    plan_tier: str,
    *,
    billing_interval: str = "monthly",
    return_url: str,
    buyer_email: str | None = None,
    embedded: bool = True,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session (embedded on-site or hosted redirect)."""
    plan = subscription_plans.get_plan(plan_tier)
    if not plan:
        raise StripeBillingError("unknown plan")
    interval = subscription_plans.normalize_billing_interval(billing_interval)

    price_id = subscription_plans.stripe_price_id(plan_tier, interval)
    static_url = subscription_plans.plan_checkout_url(plan_tier, interval)
    if not price_id and static_url:
        if embedded:
            raise StripeBillingError(
                "On-page checkout requires Stripe price IDs (STRIPE_*_PRICE_ID). "
                "Hosted checkout URLs cannot be embedded."
            )
        sep = "&" if "?" in static_url else "?"
        return {
            "embedded": False,
            "checkout_url": f"{static_url}{sep}client_reference_id={account_id}",
        }

    if not price_id:
        raise StripeBillingError(
            "Set STRIPE_*_PRICE_ID env vars for each tier/interval, or STRIPE_CHECKOUT_URL_* env URLs."
        )

    customer_id = ensure_stripe_customer(account_id, email=buyer_email)
    subscription_store.set_pending_checkout(account_id, plan.tier, billing_interval=interval)

    params: list[tuple[str, str]] = [
        ("mode", "subscription"),
        ("client_reference_id", account_id),
        ("customer", customer_id),
        *_checkout_session_payment_params(),
        ("line_items[0][price]", price_id),
        ("line_items[0][quantity]", "1"),
        ("metadata[account_id]", account_id),
        ("metadata[plan]", plan.tier),
        ("metadata[billing_interval]", interval),
        ("subscription_data[metadata][account_id]", account_id),
        ("subscription_data[metadata][plan]", plan.tier),
        ("subscription_data[metadata][billing_interval]", interval),
    ]
    if embedded:
        params.extend(
            [
                ("ui_mode", "embedded"),
                ("return_url", return_url),
            ]
        )
    else:
        params.extend(
            [
                ("success_url", return_url),
                ("cancel_url", return_url),
            ]
        )

    session = _stripe_request("POST", "/checkout/sessions", params)
    if embedded:
        client_secret = session.get("client_secret")
        if not client_secret:
            raise StripeBillingError("Stripe did not return an embedded checkout client secret")
        return {
            "embedded": True,
            "client_secret": str(client_secret),
            "session_id": str(session.get("id") or ""),
        }

    url = session.get("url")
    if not url:
        raise StripeBillingError("Stripe did not return a checkout URL")
    return {"embedded": False, "checkout_url": str(url)}


def mock_activate(
    account_id: str,
    plan_tier: str,
    *,
    billing_interval: str = "monthly",
) -> dict[str, Any]:
    if not is_billing_mock_enabled():
        raise StripeBillingError("Billing mock mode is disabled")
    from datetime import timedelta

    interval = subscription_plans.normalize_billing_interval(billing_interval)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    period_end = now + timedelta(days=30)
    subscription_store.activate_plan(
        account_id,
        plan_tier=plan_tier,
        billing_interval=interval,
        status="active",
        period_start=now.isoformat(),
        period_end=period_end.isoformat(),
        stripe_subscription_id=f"mock-sub-{uuid.uuid4()}",
    )
    invoice_store.create_mock_subscription_invoice(
        account_id, plan_tier, billing_interval=interval
    )
    return subscription_store.get_subscription(account_id)


def verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
    if not secret or not signature_header:
        return False
    parts: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts.setdefault(key.strip(), []).append(value.strip())
    timestamp = (parts.get("t") or [None])[0]
    signatures = parts.get("v1") or []
    if not timestamp or not signatures:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - ts) > 300:
        return False
    signed = f"{timestamp}.{body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def _stripe_status_to_local(status: str) -> str:
    mapping = {
        "active": "active",
        "trialing": "active",
        "past_due": "past_due",
        "unpaid": "past_due",
        "canceled": "canceled",
        "incomplete": "pending",
        "incomplete_expired": "canceled",
        "paused": "past_due",
    }
    return mapping.get(status.lower(), "inactive")


def _metadata_dict(obj: dict[str, Any]) -> dict[str, str]:
    meta = obj.get("metadata")
    if not isinstance(meta, dict):
        return {}
    return {str(k): str(v) for k, v in meta.items() if v is not None}


def _resolve_account_id_from_subscription(subscription: dict[str, Any]) -> str | None:
    sub_id = subscription.get("id")
    if sub_id:
        found = subscription_store.find_account_by_stripe_subscription(str(sub_id))
        if found:
            return found

    customer_id = subscription.get("customer")
    if customer_id:
        found = subscription_store.find_account_by_stripe_customer(str(customer_id))
        if found:
            return found

    meta = _metadata_dict(subscription)
    account_id = meta.get("account_id", "").strip()
    if account_id:
        return account_id
    return None


def _price_id_from_subscription(subscription: dict[str, Any]) -> str:
    items = subscription.get("items") or {}
    data = items.get("data") if isinstance(items, dict) else None
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            price = first.get("price")
            if isinstance(price, dict) and price.get("id"):
                return str(price["id"])
            if first.get("price"):
                return str(first.get("price"))
    return ""


def _period_end_from_subscription(subscription: dict[str, Any]) -> str | None:
    raw = subscription.get("current_period_end")
    if raw is None:
        return None
    try:
        ts = int(raw)
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return str(raw)


def apply_subscription_object(subscription: dict[str, Any]) -> str | None:
    account_id = _resolve_account_id_from_subscription(subscription)
    if not account_id:
        return None

    price_id = _price_id_from_subscription(subscription)
    tier: str | None = None
    billing_interval = "monthly"
    if price_id:
        resolved = subscription_plans.tier_and_interval_for_stripe_price_id(price_id)
        if resolved:
            tier, billing_interval = resolved

    meta = _metadata_dict(subscription)
    if meta.get("plan"):
        tier = meta.get("plan") or tier
    if meta.get("billing_interval"):
        billing_interval = subscription_plans.normalize_billing_interval(meta.get("billing_interval"))

    status = _stripe_status_to_local(str(subscription.get("status") or "inactive"))
    sub_id = subscription.get("id")
    customer_id = subscription.get("customer")

    if tier and status in ("active", "pending", "past_due"):
        subscription_store.activate_plan(
            account_id,
            plan_tier=tier,
            billing_interval=billing_interval,
            status=status,
            period_end=_period_end_from_subscription(subscription),
            stripe_customer_id=str(customer_id) if customer_id else None,
            stripe_subscription_id=str(sub_id) if sub_id else None,
        )
        if status == "past_due":
            import notification_events

            notification_events.notify_payment_issue(
                account_id,
                title="Subscription payment issue",
                body="Stripe reported a past-due subscription. Update your payment method in Billing.",
            )
    elif status == "canceled":
        subscription_store.activate_plan(
            account_id,
            plan_tier=tier or subscription_store.get_subscription(account_id)["plan_tier"],
            status="canceled",
            stripe_subscription_id=str(sub_id) if sub_id else None,
        )
    else:
        subscription_store.ensure_row(account_id)
        if customer_id:
            subscription_store.set_stripe_customer_id(account_id, str(customer_id))

    return account_id


def _resolve_account_id_from_invoice(invoice: dict[str, Any]) -> str | None:
    stripe_id = str(invoice.get("id") or "")
    if stripe_id:
        found = invoice_store.find_account_by_stripe_invoice_id(stripe_id)
        if found:
            return found

    customer_id = invoice.get("customer")
    if customer_id:
        found = subscription_store.find_account_by_stripe_customer(str(customer_id))
        if found:
            return found

    meta = _metadata_dict(invoice)
    account_id = meta.get("account_id", "").strip()
    return account_id or None


def apply_invoice_object(invoice: dict[str, Any]) -> str | None:
    account_id = _resolve_account_id_from_invoice(invoice)
    if not account_id:
        return None
    invoice_store.upsert_stripe_invoice(account_id, invoice)
    return account_id


def sync_invoices_from_stripe(account_id: str) -> list[dict[str, Any]]:
    if not is_stripe_configured():
        raise StripeBillingError("Stripe is not configured")
    sub = subscription_store.get_subscription(account_id)
    customer_id = sub.get("stripe_customer_id")
    if not customer_id:
        raise StripeBillingError("No Stripe customer linked to this account yet")

    params = urllib.parse.urlencode(
        {"customer": customer_id, "limit": "50"},
    )
    result = _stripe_request("GET", f"/invoices?{params}")
    invoices = result.get("data") or []
    synced: list[dict[str, Any]] = []
    for invoice in invoices:
        if not isinstance(invoice, dict):
            continue
        row = invoice_store.upsert_stripe_invoice(account_id, invoice)
        synced.append(invoice_store.invoice_to_api(row))
    return synced


def _apply_checkout_session_completed(session: dict[str, Any]) -> str | None:
    account_id = str(session.get("client_reference_id") or "").strip()
    if not account_id:
        meta = _metadata_dict(session)
        account_id = meta.get("account_id", "").strip()
    if not account_id:
        return None

    customer_id = session.get("customer")
    if customer_id:
        subscription_store.set_stripe_customer_id(account_id, str(customer_id))

    subscription_id = session.get("subscription")
    if subscription_id:
        sub_obj = _stripe_request("GET", f"/subscriptions/{subscription_id}")
        if isinstance(sub_obj, dict):
            return apply_subscription_object(sub_obj)
    return account_id


def handle_webhook_payload(payload: dict[str, Any]) -> str | None:
    event_id = str(payload.get("id") or "")
    event_type = str(payload.get("type") or "")
    if not event_id:
        raise StripeBillingError("missing event id")

    if not subscription_store.record_webhook_event(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    ):
        return None

    account_id: str | None = None
    data_obj = payload.get("data") or {}
    obj = data_obj.get("object") if isinstance(data_obj, dict) else None
    if not isinstance(obj, dict):
        obj = {}

    if event_type == "checkout.session.completed":
        account_id = _apply_checkout_session_completed(obj)

    if event_type.startswith("customer.subscription."):
        account_id = apply_subscription_object(obj) or account_id

    if event_type.startswith("invoice."):
        inv_account = apply_invoice_object(obj)
        account_id = account_id or inv_account

    if event_type in ("charge.succeeded", "charge.refunded", "charge.updated"):
        pay_account = billing_transaction_store.find_account_for_stripe_charge(obj)
        if pay_account:
            billing_transaction_store.upsert_stripe_charge(pay_account, obj)
            account_id = account_id or pay_account

    subscription_store.mark_webhook_processed(event_id, account_id)
    return account_id
