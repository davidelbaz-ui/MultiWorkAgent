"""Session trust and Turso connection helpers."""

from __future__ import annotations

import os
import unittest

from remote_sqlite import ephemeral_local_storage, should_trust_session_membership


class RemoteSqliteConfigTest(unittest.TestCase):
    def test_trust_session_on_vercel_without_turso(self) -> None:
        saved = {
            k: os.environ.get(k)
            for k in (
                "VERCEL",
                "TURSO_DATABASE_URL",
                "TURSO_AUTH_TOKEN",
                "AUTH_STRICT_MEMBERSHIP",
                "AUTH_TRUST_SESSION_MEMBERSHIP",
            )
        }
        try:
            os.environ["VERCEL"] = "1"
            os.environ.pop("TURSO_DATABASE_URL", None)
            os.environ.pop("TURSO_AUTH_TOKEN", None)
            os.environ.pop("AUTH_STRICT_MEMBERSHIP", None)
            os.environ.pop("AUTH_TRUST_SESSION_MEMBERSHIP", None)
            self.assertTrue(ephemeral_local_storage())
            self.assertTrue(should_trust_session_membership())
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_strict_when_turso_configured(self) -> None:
        saved = {
            k: os.environ.get(k)
            for k in ("VERCEL", "TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN")
        }
        try:
            os.environ["VERCEL"] = "1"
            os.environ["TURSO_DATABASE_URL"] = "libsql://example.turso.io"
            os.environ["TURSO_AUTH_TOKEN"] = "token"
            self.assertFalse(ephemeral_local_storage())
            self.assertFalse(should_trust_session_membership())
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
