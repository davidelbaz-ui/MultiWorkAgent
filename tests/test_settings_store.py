"""User settings persistence."""

from __future__ import annotations

import auth_store
import settings_store
from tests.postgres_test_case import PostgresStoreTestCase


class SettingsStoreTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user, self.membership = auth_store.create_account_with_owner(
            email="settings@example.com",
            password="password123",
            display_name="Settings User",
        )
        self.account_id = self.membership["account_id"]

    def test_defaults_and_patch(self) -> None:
        bundle = settings_store.settings_bundle(self.user["id"], self.account_id)
        self.assertEqual(bundle["appearance"]["theme"], "device")
        self.assertTrue(bundle["agent"]["auto_approve_enabled"])

        settings_store.update_user_settings(
            self.user["id"],
            self.account_id,
            theme="dark",
            agent_auto_approve_max_run_units=0.5,
        )
        updated = settings_store.get_user_settings(self.user["id"], self.account_id)
        self.assertEqual(updated["theme"], "dark")
        self.assertEqual(updated["agent_auto_approve_max_run_units"], 0.5)

    def test_should_auto_approve(self) -> None:
        self.assertTrue(
            settings_store.should_auto_approve_run(self.user["id"], self.account_id, 0.2)
        )
        settings_store.update_user_settings(
            self.user["id"], self.account_id, agent_auto_approve_enabled=False
        )
        self.assertFalse(
            settings_store.should_auto_approve_run(self.user["id"], self.account_id, 0.1)
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
