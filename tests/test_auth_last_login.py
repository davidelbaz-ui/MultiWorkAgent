"""Last login persistence for admin user list."""

from __future__ import annotations

import auth_store
from tests.postgres_test_case import PostgresStoreTestCase


class AuthLastLoginTests(PostgresStoreTestCase):
    def test_touch_last_login_visible_in_admin_list(self) -> None:
        user, _ = auth_store.create_account_with_owner(
            email="admin-list@example.com",
            password="password123",
            display_name="Ada Lovelace",
        )
        rows, total = auth_store.list_users_for_admin()
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["email"], "admin-list@example.com")
        self.assertEqual(rows[0]["display_name"], "Ada Lovelace")
        self.assertIsNone(rows[0]["last_login_at"])
        self.assertEqual(rows[0]["last_login_display"], "—")
        self.assertNotEqual(rows[0]["account_created_display"], "—")

        auth_store.touch_last_login(user["id"])
        updated, _ = auth_store.list_users_for_admin(query="admin-list")
        updated = updated[0]
        self.assertIsNotNone(updated["last_login_at"])
        self.assertNotEqual(updated["last_login_display"], "—")
