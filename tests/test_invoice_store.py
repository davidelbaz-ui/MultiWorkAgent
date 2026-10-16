"""Billing invoices ledger."""

from __future__ import annotations

import os
import unittest

import business_store
import invoice_store
import stripe_billing
import subscription_store
from tests.postgres_test_case import PostgresStoreTestCase


class InvoiceStoreTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account_id = "acct-inv"
        business_store.create_business(self.account_id, name="Inv Co", industry="")
        os.environ["BILLING_DEV_MOCK"] = "1"

    def test_mock_subscribe_creates_invoice(self) -> None:
        stripe_billing.mock_activate(self.account_id, "starter")
        display = invoice_store.list_for_display(self.account_id)
        self.assertEqual(len(display), 1)
        self.assertEqual(display[0]["amount"], "$499.00")
        self.assertIn("Starter", display[0]["description"])

    def test_upsert_and_webhook(self) -> None:
        subscription_store.set_square_customer_id(self.account_id, "cust_sq_1")
        payload = {
            "id": "evt-inv-1",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "inv_stripe_1",
                    "number": "1042",
                    "status": "paid",
                    "customer": "cust_sq_1",
                    "total": 4900,
                    "currency": "usd",
                    "hosted_invoice_url": "https://stripe.example/inv/1",
                    "created": 1727784000,
                    "description": "Pro subscription",
                }
            },
        }
        account_id = stripe_billing.handle_webhook_payload(payload)
        self.assertEqual(account_id, self.account_id)
        rows = invoice_store.list_invoices(self.account_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount_cents"], 4900)
        self.assertEqual(rows[0]["public_url"], "https://stripe.example/inv/1")


if __name__ == "__main__":
    unittest.main()
