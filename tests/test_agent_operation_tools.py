"""Agent integration/database operation tools."""

from __future__ import annotations

import unittest

import agent_operation_tools
import integration_api_allowlist


class IntegrationApiAllowlistTest(unittest.TestCase):
    def test_github_path_resolves(self) -> None:
        url, err = integration_api_allowlist.resolve_integration_url(
            provider_slug="github",
            path_or_url="/user",
            credentials={"access_token": "x"},
        )
        self.assertIsNone(err)
        self.assertEqual(url, "https://api.github.com/user")

    def test_blocks_private_url(self) -> None:
        url, err = integration_api_allowlist.resolve_integration_url(
            provider_slug="github",
            path_or_url="https://127.0.0.1/user",
            credentials=None,
        )
        self.assertIsNone(url)
        self.assertIn("not allowed", (err or "").lower())

    def test_wordpress_uses_site_url(self) -> None:
        url, err = integration_api_allowlist.resolve_integration_url(
            provider_slug="wordpress",
            path_or_url="/wp-json/wp/v2/posts",
            credentials={
                "api_key": "k",
                "site_url": "https://example.com",
            },
        )
        self.assertIsNone(err)
        self.assertEqual(url, "https://example.com/wp-json/wp/v2/posts")


class SqlGuardTest(unittest.TestCase):
    def test_read_only_blocks_insert(self) -> None:
        from agent_operation_tools import _sql_allowed

        ok, err = _sql_allowed("INSERT INTO t VALUES (1)", "read")
        self.assertFalse(ok)
        self.assertIn("read-only", (err or "").lower())

    def test_read_allows_select(self) -> None:
        from agent_operation_tools import _sql_allowed

        ok, err = _sql_allowed("SELECT 1", "read")
        self.assertTrue(ok)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
