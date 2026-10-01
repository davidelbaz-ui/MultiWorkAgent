"""Production config and rate limiting."""

from __future__ import annotations

import os
import unittest

import http_rate_limit
from app_config import load_app_config


class ProductionConfigTest(unittest.TestCase):
    def test_production_requires_secret(self) -> None:
        keys = ("APP_ENV", "FLASK_ENV", "FLASK_SECRET_KEY", "FLASK_DEBUG")
        saved = {k: os.environ.get(k) for k in keys}
        try:
            os.environ["APP_ENV"] = "production"
            os.environ.pop("FLASK_SECRET_KEY", None)
            os.environ.pop("FLASK_DEBUG", None)
            with self.assertRaises(RuntimeError):
                load_app_config()
            os.environ["FLASK_SECRET_KEY"] = "x" * 40
            cfg = load_app_config()
            self.assertFalse(cfg.debug)
            self.assertTrue(cfg.session_cookie_secure)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class RateLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        http_rate_limit.reset_for_tests()

    def test_blocks_after_cap(self) -> None:
        for _ in range(3):
            self.assertTrue(http_rate_limit.allow("test", "1.2.3.4", max_events=3))
        self.assertFalse(http_rate_limit.allow("test", "1.2.3.4", max_events=3))


if __name__ == "__main__":
    unittest.main()
