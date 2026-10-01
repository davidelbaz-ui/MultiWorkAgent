"""Free-tier monthly run limits."""

from __future__ import annotations

import gc
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app_db
import business_store
import run_limits
import run_store
import subscription_store
import usage_metering
from agent_executor import AgentRunResult
from run_limits import RunLimitError


class FreeTierTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._app_db = Path(self._tmpdir.name) / "app.sqlite"
        self._orig_path = app_db.APP_DB_PATH
        app_db.APP_DB_PATH = self._app_db
        app_db.init_app_database()
        self.account_id = "acct-free"
        business_store.create_business(self.account_id, name="Free Co", industry="")

    def tearDown(self) -> None:
        app_db.APP_DB_PATH = self._orig_path
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_free_tier_quota_and_block(self) -> None:
        snap = usage_metering.usage_snapshot(self.account_id)
        self.assertFalse(snap["subscription_active"])
        self.assertTrue(snap["free_tier"])
        self.assertEqual(snap["usage_quota"], 5)
        self.assertTrue(snap["can_run"])

        for i in range(5):
            run = run_store.record_chat_run(
                account_id=self.account_id,
                user_id=None,
                business_id=None,
                thread_id=f"t{i}",
                summary="hi",
                result=AgentRunResult(
                    status="completed",
                    content="ok",
                    input_tokens=100,
                    output_tokens=50,
                ),
            )
            usage_metering.meter_completed_run(self.account_id, run["id"])

        snap2 = usage_metering.usage_snapshot(self.account_id)
        self.assertEqual(snap2["usage_used"], 5.0)
        self.assertFalse(snap2["can_run"])

        with mock.patch.dict(os.environ, {"AGENT_DAILY_RUN_LIMIT": "50"}, clear=False):
            with self.assertRaises(RunLimitError) as ctx:
                run_limits.assert_can_start(self.account_id)
        self.assertEqual(ctx.exception.code, "free_tier_exhausted")


if __name__ == "__main__":
    unittest.main()
