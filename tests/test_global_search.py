"""Global search v2 (runs, connections, scope)."""

from __future__ import annotations

from pathlib import Path

import business_store
import connection_store
import database_store
import global_search
import run_store
from agent_executor import AgentRunResult
from tests.postgres_test_case import TempDirTestCase


class GlobalSearchTest(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.account_id = "acct-search"
        self.business = business_store.create_business(
            self.account_id, name="Searchable LLC", industry=""
        )
        self.business_id = self.business["id"]
        self.other = business_store.create_business(
            self.account_id, name="Other Co", industry=""
        )

    def test_scoped_run_and_connection_search(self) -> None:
        run_store.record_chat_run(
            account_id=self.account_id,
            user_id=None,
            business_id=self.business_id,
            thread_id="thread-1",
            summary="Deploy woocommerce catalog",
            result=AgentRunResult(status="completed", content="ok"),
        )
        connection_store.connect_api_key(
            self.account_id,
            self.business_id,
            provider_slug="github",
            api_key="test-key",
        )
        ext = Path(self._tmpdir.name) / "x.sqlite"
        ext.write_text("", encoding="utf-8")
        database_store.create_connection(
            self.account_id,
            self.other["id"],
            name="Other DB",
            engine="sqlite",
            database_name=str(ext),
        )

        names = {self.business_id: "Searchable LLC", self.other["id"]: "Other Co"}
        scoped = global_search.search_workspace(
            "woocommerce",
            [],
            [self.business],
            account_id=self.account_id,
            scope_business_id=self.business_id,
            business_names=names,
        )
        types = {r["type"] for r in scoped}
        self.assertIn("agent_run", types)
        self.assertNotIn("database_connection", types)

        wide = global_search.search_workspace(
            "github",
            [],
            [self.business, self.other],
            account_id=self.account_id,
            scope_business_id=None,
            business_names=names,
        )
        self.assertTrue(any(r["type"] == "integration_connection" for r in wide))


if __name__ == "__main__":
    import unittest

    unittest.main()
