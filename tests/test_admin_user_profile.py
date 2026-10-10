"""Admin user plan labels and profile helpers."""

from __future__ import annotations

import unittest

import auth_store
import admin_user_profile


class AdminPlanLabelTest(unittest.TestCase):
    def test_free_when_inactive(self) -> None:
        self.assertEqual(auth_store._plan_label("none", "inactive"), "Free")

    def test_starter_active(self) -> None:
        self.assertEqual(auth_store._plan_label("starter", "active"), "Starter")

    def test_plan_display_past_due(self) -> None:
        label = admin_user_profile.plan_display(
            {"plan_tier": "pro", "status": "past_due", "billing_interval": "monthly"}
        )
        self.assertIn("Pro", label)
        self.assertIn("past due", label)


if __name__ == "__main__":
    unittest.main()
