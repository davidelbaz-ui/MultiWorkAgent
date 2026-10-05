"""Subscription ledger + Square webhook application."""

from __future__ import annotations

import os
import unittest

import business_store
import square_billing
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
        self.assertEqual(summary["usage_quota"], 150)
        self.assertTrue(subscription_store.is_subscription_active(self.account_id))

    def test_webhook_idempotent(self) -> None:
        payload = {
            "event_id": "evt-1",
            "type": "subscription.updated",
            "data": {
                "object": {
                    "subscription": {
                        "id": "sub_abc",
                        "customer_id": "cust_1",
                        "status": "ACTIVE",
                        "plan_variation_id": "unknown-var",
                        "note": f"account_id={self.account_id};plan=pro",
                        "charged_through_date": "2026-11-01",
                    }
                }
            },
        }
        subscription_store.set_square_customer_id(self.account_id, "cust_1")
        account_id = square_billing.apply_subscription_object(
            payload["data"]["object"]["subscription"]
        )
        self.assertEqual(account_id, self.account_id)
        sub = subscription_store.get_subscription(self.account_id)
        self.assertEqual(sub["plan_tier"], "pro")
        self.assertEqual(sub["status"], "active")

        self.assertEqual(square_billing.handle_webhook_payload(payload), self.account_id)
        self.assertIsNone(square_billing.handle_webhook_payload(payload))


class SquareBillingMockTest(PostgresStoreTestCase):
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
        square_billing.mock_activate(self.account_id, "starter")
        self.assertTrue(subscription_store.is_subscription_active(self.account_id))


if __name__ == "__main__":
    unittest.main()
