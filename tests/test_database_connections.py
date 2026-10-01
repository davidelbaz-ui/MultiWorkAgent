"""Database connection store + introspection (SQLite file)."""

from __future__ import annotations

import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app_db
import business_store
import database_introspect
import database_store


class DatabaseConnectionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._app_db = Path(self._tmpdir.name) / "app.sqlite"
        self._external_db = Path(self._tmpdir.name) / "external.sqlite"
        ext = sqlite3.connect(self._external_db)
        ext.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, label TEXT)")
        ext.commit()
        ext.close()

        self._orig_path = app_db.APP_DB_PATH
        app_db.APP_DB_PATH = self._app_db
        app_db.init_app_database()

        self.account_id = "acct-test"
        self.business = business_store.create_business(
            self.account_id, name="Test Biz", industry=""
        )
        self.business_id = self.business["id"]

    def tearDown(self) -> None:
        app_db.APP_DB_PATH = self._orig_path
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass

    def test_introspect_sqlite_file(self) -> None:
        schema = database_introspect.test_and_introspect(
            engine="sqlite",
            host="",
            port=None,
            database_name=str(self._external_db),
            username="",
            password="",
        )
        self.assertEqual(schema["engine"], "sqlite")
        self.assertGreaterEqual(schema["table_count"], 1)
        names = [t["name"] for t in schema["tables"]]
        self.assertIn("widgets", names)

    def test_create_list_delete_connection(self) -> None:
        row = database_store.create_connection(
            self.account_id,
            self.business_id,
            name="Local SQLite",
            engine="sqlite",
            host="",
            port=None,
            database_name=str(self._external_db),
            username="",
            password="",
            access_mode="read",
        )
        self.assertEqual(row["name"], "Local SQLite")
        self.assertIsNotNone(row.get("schema"))
        listed = database_store.list_connections(
            self.account_id, business_id=self.business_id
        )
        self.assertEqual(len(listed), 1)
        api = database_store.connection_to_api(listed[0])
        self.assertIn("tables", api["schema_summary"])

        synced = database_store.sync_schema(
            self.account_id, self.business_id, row["id"]
        )
        self.assertIsNotNone(synced.get("schema_synced_at"))

        self.assertTrue(
            database_store.delete_connection(
                self.account_id, self.business_id, row["id"]
            )
        )
        self.assertEqual(
            database_store.list_connections(
                self.account_id, business_id=self.business_id
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
