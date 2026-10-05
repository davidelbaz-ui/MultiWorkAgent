"""Usage metering against plan quota and top-up balance."""

from __future__ import annotations

import os
import unittest

import app_db
import business_store
import run_store
import subscription_store
import usage_metering
from agent_executor import AgentRunResult
from tests.postgres_test_case import PostgresStoreTestCase


class UsageMeteringTest(PostgresStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account_id = "acct-usage"
        business_store.create_business(self.account_id, name="Usage Co", industry="")
        os.environ["BILLING_DEV_MOCK"] = "1"
        subscription_store.activate_plan(self.account_id, plan_tier="starter", status="active")

    def test_meter_plan_then_top_up(self) -> None:
        usage_metering.add_top_up_runs(self.account_id, 2)
        snap = usage_metering.usage_snapshot(self.account_id)
        self.assertEqual(snap["usage_quota"], 50)
        self.assertEqual(snap["top_up_balance"], 2.0)

        run = run_store.record_chat_run(
            account_id=self.account_id,
            user_id=None,
            business_id=None,
            thread_id="t1",
            summary="hello",
            result=AgentRunResult(
                status="completed",
                content="ok",
                input_tokens=30_000,
                output_tokens=2_000,
            ),
        )
        snap2 = usage_metering.usage_snapshot(self.account_id)
        self.assertEqual(snap2["usage_used"], 1.0)
        self.assertEqual(snap2["plan_remaining"], 49.0)

        with app_db.connect() as conn:
            row = conn.execute(
                "SELECT usage_metered_at FROM agent_runs WHERE id = ?",
                (run["id"],),
            ).fetchone()
        self.assertTrue(row["usage_metered_at"])

        usage_metering.meter_completed_run(self.account_id, run["id"])
        snap3 = usage_metering.usage_snapshot(self.account_id)
        self.assertEqual(snap3["usage_used"], 1.0)

        with app_db.connect() as conn:
            conn.execute(
                """
                UPDATE account_subscriptions
                SET plan_runs_consumed = 50, top_up_balance_runs = 0.5
                WHERE account_id = ?
                """,
                (self.account_id,),
            )

        run_store.record_chat_run(
            account_id=self.account_id,
            user_id=None,
            business_id=None,
            thread_id="t2",
            summary="more",
            result=AgentRunResult(
                status="completed",
                content="ok",
                input_tokens=30_000,
                output_tokens=2_000,
            ),
        )
        snap4 = usage_metering.usage_snapshot(self.account_id)
        self.assertEqual(snap4["usage_used"], 50.0)
        self.assertEqual(snap4["top_up_balance"], 0.0)

    def test_quota_blocks_when_exhausted(self) -> None:
        with app_db.connect() as conn:
            conn.execute(
                """
                UPDATE account_subscriptions
                SET plan_runs_consumed = 50, top_up_balance_runs = 0
                WHERE account_id = ?
                """,
                (self.account_id,),
            )
        snap = usage_metering.usage_snapshot(self.account_id)
        self.assertFalse(snap["can_run"])


if __name__ == "__main__":
    unittest.main()
