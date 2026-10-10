"""Square subscription checkout + webhook handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

import billing_transaction_store
import invoice_store
import subscription_plans
import subscription_store

SQUARE_API_VERSION = "2024-10-17"


class SquareBillingError(Exception):
    pass


def is_billing_mock_enabled() -> bool:
    return os.environ.get("SQUARE_MOCK", "").strip() in ("1", "true", "yes") or os.environ.get(
        "BILLING_DEV_MOCK", ""
    ).strip() in ("1", "true", "yes")


def is_square_configured() -> bool:
    token = _access_token()
    location = os.environ.get("SQUARE_LOCATION_ID", "").strip()
    if not token or not location:
        return False
    for tier in subscription_plans.PLANS:
        for interval in subscription_plans.BILLING_INTERVALS:
            if subscription_plans.plan_variation_id(tier, interval) or subscription_plans.plan_checkout_url(
                tier, interval
            ):
                return True
    return False


def billing_mode() -> str:
    if is_square_configured():
        return "square"
    if is_billing_mock_enabled():
        return "mock"
    return "unconfigured"


def _access_token() -> str:
    return os.environ.get("SQUARE_ACCESS_TOKEN", "").strip()


def _api_base() -> str:
    env = os.environ.get("SQUARE_ENVIRONMENT", "sandbox").strip().lower()
    if env in ("production", "prod"):
        return "https://connect.squareup.com"
    return "https://connect.squareupsandbox.com"


def _square_request(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = _access_token()
    if not token:
        raise SquareBillingError("SQUARE_ACCESS_TOKEN is not set")
    url = f"{_api_base()}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Square-Version": SQUARE_API_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SquareBillingError(f"Square API error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise SquareBillingError(str(exc)) from exc

    parsed = json.loads(raw) if raw else {}
    if not isinstance(parsed, dict):
        raise SquareBillingError("unexpected Square response")
    if parsed.get("errors"):
        raise SquareBillingError(json.dumps(parsed["errors"], ensure_ascii=False))
    return parsed


def ensure_square_customer(account_id: str, *, email: str | None = None) -> str:
    sub = subscription_store.get_subscription(account_id)
    if sub["square_customer_id"]:
        return sub["square_customer_id"]

    body: dict[str, Any] = {
        "idempotency_key": str(uuid.uuid4()),
        "given_name": "Account",
        "reference_id": account_id[:255],
    }
    if email:
        body["email_address"] = email.strip()
    result = _square_request("POST", "/v2/customers", body)
    customer = result.get("customer") or {}
    customer_id = customer.get("id")
    if not customer_id:
        raise SquareBillingError("Square did not return a customer id")
    subscription_store.set_square_customer_id(account_id, customer_id)
    return customer_id


def create_checkout_url(
    account_id: str,
    plan_tier: str,
    *,
    billing_interval: str = "monthly",
    redirect_url: str,
    buyer_email: str | None = None,
) -> str:
    plan = subscription_plans.get_plan(plan_tier)
    if not plan:
        raise SquareBillingError("unknown plan")
    interval = subscription_plans.normalize_billing_interval(billing_interval)

    static_url = subscription_plans.plan_checkout_url(plan_tier, interval)
    if static_url and not subscription_plans.plan_variation_id(plan_tier, interval):
        sep = "&" if "?" in static_url else "?"
        return f"{static_url}{sep}reference_id={account_id}"

    variation_id = subscription_plans.plan_variation_id(plan_tier, interval)
    location_id = os.environ.get("SQUARE_LOCATION_ID", "").strip()
    if not variation_id or not location_id:
        raise SquareBillingError(
            "Set SQUARE_LOCATION_ID and plan variation IDs (monthly and annual), or SQUARE_CHECKOUT_URL_* env URLs."
        )

    ensure_square_customer(account_id, email=buyer_email)
    subscription_store.set_pending_checkout(account_id, plan.tier, billing_interval=interval)

    body = {
        "idempotency_key": str(uuid.uuid4()),
        "checkout_options": {
            "subscription_plan_variation_id": variation_id,
            "redirect_url": redirect_url,
            "merchant_support_email": buyer_email or os.environ.get("SQUARE_SUPPORT_EMAIL", ""),
        },
        "pre_populated_data": {},
        "payment_note": f"account_id={account_id};plan={plan.tier};interval={interval}"[:500],
    }
    if buyer_email:
        body["pre_populated_data"]["buyer_email"] = buyer_email.strip()

    result = _square_request("POST", "/v2/online-checkout/payment-links", body)
    link = result.get("payment_link") or {}
    url = link.get("long_url") or link.get("url")
    if not url:
        raise SquareBillingError("Square did not return a checkout URL")
    return url


def mock_activate(
    account_id: str,
    plan_tier: str,
    *,
    billing_interval: str = "monthly",
) -> dict[str, Any]:
    if not is_billing_mock_enabled():
        raise SquareBillingError("Billing mock mode is disabled")
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
        square_subscription_id=f"mock-sub-{uuid.uuid4()}",
    )
    invoice_store.create_mock_subscription_invoice(
        account_id, plan_tier, billing_interval=interval
    )
    return subscription_store.get_subscription(account_id)


def verify_webhook_signature(body: bytes, signature_header: str, notification_url: str) -> bool:
    key = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "").strip()
    if not key:
        return False
    if not signature_header:
        return False
    message = notification_url.encode("utf-8") + body
    digest = hmac.new(key.encode("utf-8"), message, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature_header.strip())


def _square_status_to_local(status: str) -> str:
    mapping = {
        "ACTIVE": "active",
        "PENDING": "pending",
        "CANCELED": "canceled",
        "DEACTIVATED": "canceled",
        "PAUSED": "past_due",
    }
    return mapping.get(status.upper(), "inactive")


def _resolve_account_id_from_subscription(subscription: dict[str, Any]) -> str | None:
    sub_id = subscription.get("id")
    if sub_id:
        found = subscription_store.find_account_by_square_subscription(sub_id)
        if found:
            return found

    customer_id = subscription.get("customer_id")
    if customer_id:
        found = subscription_store.find_account_by_square_customer(customer_id)
        if found:
            return found

    note = subscription.get("note") or subscription.get("source") or ""
    if isinstance(note, dict):
        note = json.dumps(note)
    text = str(note)
    if "account_id=" in text:
        fragment = text.split("account_id=", 1)[1]
        account_id = fragment.split(";", 1)[0].split(",", 1)[0].strip()
        if account_id:
            return account_id
    return None


def _period_end_from_subscription(subscription: dict[str, Any]) -> str | None:
    for key in ("charged_through_date", "paid_until_date", "end_date"):
        raw = subscription.get(key)
        if raw:
            return str(raw)
    return None


def apply_subscription_object(subscription: dict[str, Any]) -> str | None:
    account_id = _resolve_account_id_from_subscription(subscription)
    if not account_id:
        return None

    variation_id = ""
    plan_variation = subscription.get("plan_variation_id")
    if plan_variation:
        variation_id = str(plan_variation)
    else:
        phases = subscription.get("phases") or []
        if phases and isinstance(phases[0], dict):
            variation_id = str(phases[0].get("plan_variation_id") or "")

    tier: str | None = None
    billing_interval = "monthly"
    if variation_id:
        resolved = subscription_plans.tier_and_interval_for_variation_id(variation_id)
        if resolved:
            tier, billing_interval = resolved

    note = subscription.get("note") or subscription.get("source") or ""
    if isinstance(note, dict):
        note = json.dumps(note)
    note_text = str(note)
    note_tier, note_interval = subscription_plans.parse_plan_from_payment_note(note_text)
    if note_tier:
        tier = note_tier
    if note_interval:
        billing_interval = note_interval
    elif not tier:
        if "plan=starter" in note_text:
            tier = "starter"
        elif "plan=pro" in note_text:
            tier = "pro"
        elif "plan=enterprise" in note_text:
            tier = "enterprise"

    status = _square_status_to_local(str(subscription.get("status") or "INACTIVE"))
    sub_id = subscription.get("id")
    customer_id = subscription.get("customer_id")

    if tier and status in ("active", "pending", "past_due"):
        subscription_store.activate_plan(
            account_id,
            plan_tier=tier,
            billing_interval=billing_interval,
            status=status,
            period_end=_period_end_from_subscription(subscription),
            square_customer_id=str(customer_id) if customer_id else None,
            square_subscription_id=str(sub_id) if sub_id else None,
        )
        if status == "past_due":
            import notification_events

            notification_events.notify_payment_issue(
                account_id,
                title="Subscription payment issue",
                body="Square reported a past-due subscription. Update your payment method in Billing.",
            )
    elif status == "canceled":
        subscription_store.activate_plan(
            account_id,
            plan_tier=tier or subscription_store.get_subscription(account_id)["plan_tier"],
            status="canceled",
            square_subscription_id=str(sub_id) if sub_id else None,
        )
    else:
        subscription_store.ensure_row(account_id)
        if customer_id:
            subscription_store.set_square_customer_id(account_id, str(customer_id))

    return account_id


def _resolve_account_id_from_invoice(invoice: dict[str, Any]) -> str | None:
    square_id = str(invoice.get("id") or "")
    if square_id:
        found = invoice_store.find_account_by_square_invoice_id(square_id)
        if found:
            return found

    recipient = invoice.get("primary_recipient") or {}
    if isinstance(recipient, dict):
        customer_id = recipient.get("customer_id")
        if customer_id:
            found = subscription_store.find_account_by_square_customer(str(customer_id))
            if found:
                return found

    return None


def apply_invoice_object(invoice: dict[str, Any]) -> str | None:
    account_id = _resolve_account_id_from_invoice(invoice)
    if not account_id:
        return None
    invoice_store.upsert_square_invoice(account_id, invoice)
    return account_id


def sync_invoices_from_square(account_id: str) -> list[dict[str, Any]]:
    if not is_square_configured():
        raise SquareBillingError("Square is not configured")
    sub = subscription_store.get_subscription(account_id)
    customer_id = sub.get("square_customer_id")
    if not customer_id:
        raise SquareBillingError("No Square customer linked to this account yet")

    location_id = os.environ.get("SQUARE_LOCATION_ID", "").strip()
    body = {
        "query": {
            "filter": {
                "customer_ids": [customer_id],
                "location_ids": [location_id],
            },
            "sort": {
                "field": "INVOICE_SORT_DATE",
                "order": "DESC",
            },
        },
        "limit": 50,
    }
    result = _square_request("POST", "/v2/invoices/search", body)
    invoices = result.get("invoices") or []
    synced: list[dict[str, Any]] = []
    for invoice in invoices:
        if not isinstance(invoice, dict):
            continue
        row = invoice_store.upsert_square_invoice(account_id, invoice)
        synced.append(invoice_store.invoice_to_api(row))
    return synced


def handle_webhook_payload(payload: dict[str, Any]) -> str | None:
    event_id = str(payload.get("event_id") or "")
    event_type = str(payload.get("type") or "")
    if not event_id:
        raise SquareBillingError("missing event_id")

    if not subscription_store.record_webhook_event(
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    ):
        return None

    account_id: str | None = None
    data = payload.get("data") or {}
    obj = data.get("object") or {}

    if event_type.startswith("subscription."):
        subscription = obj.get("subscription") or obj
        if isinstance(subscription, dict):
            account_id = apply_subscription_object(subscription)

    if event_type.startswith("invoice."):
        invoice = obj.get("invoice") or obj
        if isinstance(invoice, dict):
            inv_account = apply_invoice_object(invoice)
            account_id = account_id or inv_account

    if event_type.startswith("payment."):
        payment = obj.get("payment") or obj
        if isinstance(payment, dict):
            pay_account = billing_transaction_store.find_account_for_payment(payment)
            if pay_account:
                billing_transaction_store.upsert_square_payment(pay_account, payment)
                try:
                    import account_activity_store

                    account_activity_store.record(
                        pay_account,
                        category="billing",
                        action="payment_webhook",
                        summary=f"Square payment · {payment.get('status')}",
                        detail={"event_type": event_type, "payment_id": payment.get("id")},
                    )
                except Exception:
                    pass
                account_id = account_id or pay_account

    if event_type.startswith("refund."):
        refund = obj.get("refund") or obj
        if isinstance(refund, dict):
            pay_account = account_id
            if not pay_account:
                payment_id = str(refund.get("payment_id") or "")
                if payment_id:
                    pay_account = billing_transaction_store.find_account_by_square_payment_id(
                        payment_id
                    )
            if pay_account:
                billing_transaction_store.upsert_square_refund(pay_account, refund)
                try:
                    import account_activity_store

                    account_activity_store.record(
                        pay_account,
                        category="billing",
                        action="refund_webhook",
                        summary=f"Square refund · {refund.get('status')}",
                        detail={"event_type": event_type, "refund_id": refund.get("id")},
                    )
                except Exception:
                    pass
                account_id = account_id or pay_account

    subscription_store.mark_webhook_processed(event_id, account_id)
    return account_id
