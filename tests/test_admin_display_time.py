"""Admin Eastern time formatting."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

import admin_display_time


class AdminDisplayTimeTest(unittest.TestCase):
    def test_winter_uses_est(self) -> None:
        # 18:00 UTC = 1:00 PM EST in January
        text = admin_display_time.format_eastern("2026-01-15T18:00:00+00:00")
        self.assertIn("EST", text)
        self.assertIn("01:00 PM", text)

    def test_summer_uses_edt(self) -> None:
        text = admin_display_time.format_eastern("2026-07-15T18:00:00+00:00")
        self.assertIn("EDT", text)

    def test_empty(self) -> None:
        self.assertEqual(admin_display_time.format_eastern(None), "—")


if __name__ == "__main__":
    unittest.main()
