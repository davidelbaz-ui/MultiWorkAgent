"""Contact support persistence (support.sqlite)."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

import auth_store
import app_db
import support_db
import support_store


class SupportStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._app_db = Path(self._tmpdir.name) / "app.sqlite"
        self._support_db = Path(self._tmpdir.name) / "support.sqlite"
        self._orig_app_path = app_db.APP_DB_PATH
        self._orig_support_path = support_db.SUPPORT_DB_PATH
        app_db.APP_DB_PATH = self._app_db
        support_db.SUPPORT_DB_PATH = self._support_db
        app_db.init_app_database()
        support_store.bootstrap()
        self.user, self.membership = auth_store.create_account_with_owner(
            email="support@example.com",
            password="password123",
            display_name="Support User",
        )
        self.account_id = self.membership["account_id"]

    def tearDown(self) -> None:
        app_db.APP_DB_PATH = self._orig_app_path
        support_db.SUPPORT_DB_PATH = self._orig_support_path
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_thread_welcome_and_user_message(self) -> None:
        rows = support_store.list_messages(self.account_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sender_type"], support_store.SENDER_SYSTEM)

        support_store.add_user_message(
            account_id=self.account_id,
            user_id=self.user["id"],
            body="  Need help with OAuth  ",
        )
        rows = support_store.list_messages(self.account_id)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["body"], "Need help with OAuth")

        api = support_store.message_to_api(rows[1], viewer_user_id=self.user["id"])
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
        thread = support_store.get_or_create_thread(self.account_id)
        self.assertIsNotNone(thread["id"])
        fresh = support_store.list_messages(self.account_id)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]["sender_type"], support_store.SENDER_SYSTEM)

    def test_empty_message_rejected(self) -> None:
        with self.assertRaises(ValueError):
            support_store.add_user_message(
                account_id=self.account_id,
                user_id=self.user["id"],
                body="   ",
            )


if __name__ == "__main__":
    unittest.main()
