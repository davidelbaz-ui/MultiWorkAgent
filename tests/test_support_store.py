"""Contact support persistence."""

from __future__ import annotations

import auth_store
import support_store
from tests.postgres_test_case import PostgresStoreTestCase


class SupportStoreTests(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        support_store.bootstrap()
        self.user, self.membership = auth_store.create_account_with_owner(
            email="support@example.com",
            password="password123",
            display_name="Support User",
        )
        self.account_id = self.membership["account_id"]

    def test_thread_starts_empty_reminder_is_not_stored(self) -> None:
        self.assertIsNone(support_store.get_thread(self.account_id))
        rows = support_store.list_messages(self.account_id)
        self.assertEqual(rows, [])
        self.assertIsNone(support_store.get_thread(self.account_id))
        self.assertIn("48 hours", support_store.support_reminder_text())

        support_store.add_user_message(
            account_id=self.account_id,
            user_id=self.user["id"],
            body="  Need help with OAuth  ",
        )
        rows = support_store.list_messages(self.account_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["body"], "Need help with OAuth")

        api = support_store.message_to_api(rows[0], viewer_user_id=self.user["id"])
        self.assertTrue(api["is_mine"])
        self.assertEqual(api["sender_label"], "You")

    def test_support_reply_and_delete_account_threads(self) -> None:
        support_store.add_support_reply(
            account_id=self.account_id,
            body="We are looking into this.",
        )
        rows = support_store.list_messages(self.account_id)
        self.assertEqual(rows[-1]["sender_type"], support_store.SENDER_SUPPORT)

        removed = support_store.delete_threads_for_account(self.account_id)
        self.assertEqual(removed, 1)
        self.assertIsNone(support_store.get_thread(self.account_id))
        fresh = support_store.list_messages(self.account_id)
        self.assertEqual(fresh, [])

    def test_empty_message_rejected(self) -> None:
        with self.assertRaises(ValueError):
            support_store.add_user_message(
                account_id=self.account_id,
                user_id=self.user["id"],
                body="   ",
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
