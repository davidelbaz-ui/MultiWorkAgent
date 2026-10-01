"""Notification feed and preferences."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

import app_db
import business_store
import notification_events
import notification_store


class NotificationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._app_db = Path(self._tmpdir.name) / "app.sqlite"
        self._orig_path = app_db.APP_DB_PATH
        app_db.APP_DB_PATH = self._app_db
        app_db.init_app_database()
        self.account_id = "acct-notify"
        business_store.create_business(self.account_id, name="Notify Co", industry="")

    def tearDown(self) -> None:
        app_db.APP_DB_PATH = self._orig_path
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

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


if __name__ == "__main__":
    unittest.main()
