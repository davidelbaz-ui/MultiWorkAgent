"""Signed OAuth state tokens for serverless deployments."""

from __future__ import annotations

import os
import unittest
from unittest import mock

import login_oauth_state_store
import oauth_state_store
import signed_oauth_state


class SignedOAuthStateTests(unittest.TestCase):
    def test_login_state_roundtrip(self) -> None:
        env = {"FLASK_SECRET_KEY": "test-secret-key-for-oauth-state"}
        with mock.patch.dict(os.environ, env, clear=False):
            token = login_oauth_state_store.create_state(
                provider="google",
                next_url="/agent",
            )
            row = login_oauth_state_store.pop_state(token)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["provider"], "google")
        self.assertEqual(row["next_url"], "/agent")

    def test_integration_state_roundtrip(self) -> None:
        env = {"FLASK_SECRET_KEY": "test-secret-key-for-oauth-state"}
        with mock.patch.dict(os.environ, env, clear=False):
            token = oauth_state_store.create_state(
                account_id="acc-1",
                business_id="biz-1",
                provider_slug="github",
            )
            row = oauth_state_store.pop_state(token)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["account_id"], "acc-1")
        self.assertEqual(row["provider_slug"], "github")

    def test_tampered_token_rejected(self) -> None:
        env = {"FLASK_SECRET_KEY": "test-secret-key-for-oauth-state"}
        with mock.patch.dict(os.environ, env, clear=False):
            token = login_oauth_state_store.create_state(provider="google", next_url="")
            bad = token[:-1] + ("a" if token[-1] != "a" else "b")
            self.assertIsNone(login_oauth_state_store.pop_state(bad))

    def test_wrong_salt_rejected(self) -> None:
        env = {"FLASK_SECRET_KEY": "test-secret-key-for-oauth-state"}
        with mock.patch.dict(os.environ, env, clear=False):
            token = signed_oauth_state.issue_signed_state(
                salt="wrong-salt",
                payload={"provider": "google", "next_url": ""},
            )
            self.assertIsNone(login_oauth_state_store.pop_state(token))


if __name__ == "__main__":
    unittest.main()
