"""Notification feed and preferences."""

from __future__ import annotations

import business_store
import notification_events
import notification_store
from tests.postgres_test_case import PostgresStoreTestCase


class NotificationsTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account_id = "acct-notify"
        business_store.create_business(self.account_id, name="Notify Co", industry="")

    def test_dedupe_key(self) -> None:
        row = notification_store.create_notification(
            self.account_id,
            kind="daily_limit",
            title="Daily limit",
            body="Paused",
            dedupe_key="daily:1",
        )
        self.assertIsNotNone(row)
        again = notification_store.create_notification(
            self.account_id,
            kind="daily_limit",
            title="Daily limit",
            body="Paused",
            dedupe_key="daily:1",
        )
        self.assertIsNotNone(again)
        self.assertEqual(again["id"], row["id"])
        self.assertEqual(notification_store.unread_count(self.account_id), 1)

    def test_run_finished_respects_prefs(self) -> None:
        notification_store.update_prefs(self.account_id, run_done=False)
        notification_events.notify_run_finished(
            self.account_id,
            {"status": "completed", "summary": "Hi", "thread_id": "t1", "run_units": 1},
        )
        self.assertEqual(notification_store.unread_count(self.account_id), 0)

        notification_store.update_prefs(self.account_id, run_done=True)
        notification_events.notify_run_finished(
            self.account_id,
            {"status": "error", "summary": "Fail", "thread_id": "t1", "error_code": "timeout"},
        )
        self.assertEqual(notification_store.unread_count(self.account_id), 1)
        items = notification_store.list_notifications(self.account_id)
        self.assertEqual(items[0]["kind"], "run_failed")

    def test_delete_one_and_all(self) -> None:
        n1 = notification_store.create_notification(
            self.account_id,
            kind="run_done",
            title="One",
            body="A",
        )
        notification_store.create_notification(
            self.account_id,
            kind="run_done",
            title="Two",
            body="B",
        )
        self.assertIsNotNone(n1)
        self.assertTrue(notification_store.delete_notification(self.account_id, n1["id"]))
        self.assertEqual(len(notification_store.list_notifications(self.account_id)), 1)
        deleted = notification_store.delete_all_notifications(self.account_id)
        self.assertEqual(deleted, 1)
        self.assertEqual(notification_store.unread_count(self.account_id), 0)


if __name__ == "__main__":
    import unittest

    unittest.main()
