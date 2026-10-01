"""OAuth login identity linking."""

from __future__ import annotations

import gc
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import auth_store
import app_db


class LoginOAuthStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._app_db = Path(self._tmpdir.name) / "app.sqlite"
        self._orig_path = app_db.APP_DB_PATH
        app_db.APP_DB_PATH = self._app_db
        auth_store.bootstrap()

    def tearDown(self) -> None:
        app_db.APP_DB_PATH = self._orig_path
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_create_account_with_oauth_and_relogin(self) -> None:
        user, membership = auth_store.create_account_with_oauth(
            email="owner@example.com",
            display_name="Owner",
            provider="google",
            provider_subject="google-sub-1",
        )
        self.assertEqual(user["email"], "owner@example.com")
        self.assertEqual(membership["role"], "owner")

        again_user, again_membership = auth_store.login_with_oauth_profile(
            {
                "provider": "google",
                "subject": "google-sub-1",
                "email": "owner@example.com",
                "display_name": "Owner",
                "email_verified": True,
            }
        )
        self.assertEqual(again_user["id"], user["id"])
        self.assertEqual(again_membership["account_id"], membership["account_id"])

    def test_oauth_links_existing_email_user(self) -> None:
        user, _ = auth_store.create_account_with_owner(
            email="team@example.com",
            password="password123",
            display_name="Team",
        )
        linked, membership = auth_store.create_account_with_oauth(
            email="team@example.com",
            display_name="Team Microsoft",
            provider="microsoft",
            provider_subject="ms-sub-9",
        )
        self.assertEqual(linked["id"], user["id"])
        self.assertIsNotNone(membership)


class LoginOAuthConfiguredTests(unittest.TestCase):
    def test_configured_when_env_set(self) -> None:
        import login_oauth

        env = {
            "GOOGLE_LOGIN_CLIENT_ID": "g-id",
            "GOOGLE_LOGIN_CLIENT_SECRET": "g-secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(login_oauth.is_provider_configured("google"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(login_oauth.is_provider_configured("google"))


if __name__ == "__main__":
    unittest.main()
