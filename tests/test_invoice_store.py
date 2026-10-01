"""Billing invoices ledger."""

from __future__ import annotations

import gc
import os
import tempfile
import unittest
from pathlib import Path

import app_db
import business_store
import invoice_store
import square_billing
import subscription_store


class InvoiceStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._app_db = Path(self._tmpdir.name) / "app.sqlite"
        self._orig_path = app_db.APP_DB_PATH
        app_db.APP_DB_PATH = self._app_db
        app_db.init_app_database()
        self.account_id = "acct-inv"
        business_store.create_business(self.account_id, name="Inv Co", industry="")
        os.environ["BILLING_DEV_MOCK"] = "1"

    def tearDown(self) -> None:
        app_db.APP_DB_PATH = self._orig_path
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_mock_subscribe_creates_invoice(self) -> None:
        square_billing.mock_activate(self.account_id, "starter")
        display = invoice_store.list_for_display(self.account_id)
        self.assertEqual(len(display), 1)
        self.assertEqual(display[0]["amount"], "$19.00")
        self.assertIn("Starter", display[0]["description"])

    def test_upsert_and_webhook(self) -> None:
        subscription_store.set_square_customer_id(self.account_id, "cust_sq_1")
        payload = {
            "event_id": "evt-inv-1",
            "type": "invoice.payment_made",
            "data": {
                "object": {
                    "invoice": {
                        "id": "inv_square_1",
                        "invoice_number": "1042",
                        "status": "PAID",
                        "title": "Pro subscription",
                        "created_at": "2026-10-01T12:00:00Z",
                        "updated_at": "2026-10-01T12:05:00Z",
                        "public_url": "https://square.example/inv/1",
                        "primary_recipient": {"customer_id": "cust_sq_1"},
                        "payment_requests": [
                            {
                                "computed_amount_money": {
                                    "amount": 4900,
                                    "currency": "USD",
                                }
                            }
                        ],
                    }
                }
            },
        }
        account_id = square_billing.handle_webhook_payload(payload)
        self.assertEqual(account_id, self.account_id)
        rows = invoice_store.list_invoices(self.account_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount_cents"], 4900)
        self.assertEqual(rows[0]["public_url"], "https://square.example/inv/1")


if __name__ == "__main__":
    unittest.main()
