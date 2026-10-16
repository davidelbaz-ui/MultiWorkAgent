"""Subscription ledger + Stripe webhook application."""

from __future__ import annotations

import os
import unittest

import business_store
import stripe_billing
import subscription_store
from tests.postgres_test_case import PostgresStoreTestCase


class SubscriptionStoreTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account_id = "acct-bill-1"
        business_store.create_business(self.account_id, name="Bill Co", industry="")

    def test_activate_and_summary(self) -> None:
        subscription_store.activate_plan(self.account_id, plan_tier="starter", status="active")
        summary = subscription_store.billing_summary(self.account_id)
        self.assertEqual(summary["plan"], "Starter")
        self.assertEqual(summary["usage_quota"], 300)
        self.assertTrue(subscription_store.is_subscription_active(self.account_id))

    def test_webhook_idempotent(self) -> None:
        payload = {
            "id": "evt-1",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_abc",
                    "customer": "cust_1",
                    "status": "active",
                    "metadata": {"account_id": self.account_id, "plan": "pro"},
                    "current_period_end": 1793577600,
                    "items": {"data": [{"price": {"id": "price_unknown"}}]},
                }
            },
        }
        subscription_store.set_stripe_customer_id(self.account_id, "cust_1")
        account_id = stripe_billing.apply_subscription_object(payload["data"]["object"])
        self.assertEqual(account_id, self.account_id)
        sub = subscription_store.get_subscription(self.account_id)
        self.assertEqual(sub["plan_tier"], "pro")
        self.assertEqual(sub["status"], "active")

        self.assertEqual(stripe_billing.handle_webhook_payload(payload), self.account_id)
        self.assertIsNone(stripe_billing.handle_webhook_payload(payload))


class StripeBillingMockTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account_id = "acct-mock"
        business_store.create_business(self.account_id, name="Mock", industry="")
        self._orig_mock = os.environ.get("BILLING_DEV_MOCK")
        os.environ["BILLING_DEV_MOCK"] = "1"

    def tearDown(self) -> None:
        if self._orig_mock is None:
            os.environ.pop("BILLING_DEV_MOCK", None)
        else:
            os.environ["BILLING_DEV_MOCK"] = self._orig_mock
        super().tearDown()

    def test_mock_activate(self) -> None:
        stripe_billing.mock_activate(self.account_id, "starter")
        self.assertTrue(subscription_store.is_subscription_active(self.account_id))


if __name__ == "__main__":
    unittest.main()
