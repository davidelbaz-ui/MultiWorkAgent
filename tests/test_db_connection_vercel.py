import os
import unittest
from unittest import mock

from db_connection import database_env_diagnostics, database_url, deployment_database_error


class VercelDatabaseEnvTests(unittest.TestCase):
    def test_local_database_url_only(self):
        env = {
            "VERCEL": "1",
            "VERCEL_ENV": "production",
            "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(database_url(), "")
            err = deployment_database_error()
            self.assertIsNotNone(err)
            self.assertIn("POSTGRES_URL", err)
            diag = database_env_diagnostics()
            self.assertFalse(diag["has_remote_url"])
            self.assertEqual(diag["env_keys"]["POSTGRES_URL"], "missing")
            self.assertEqual(diag["env_keys"]["DATABASE_URL"], "local")
            self.assertTrue(any("Delete DATABASE_URL" in s for s in diag["fix_steps"]))

    def test_postgres_url_wins_over_local_database_url(self):
        env = {
            "VERCEL": "1",
            "VERCEL_ENV": "production",
            "POSTGRES_URL": "postgresql://u:p@ep-example.neon.tech/neondb",
            "DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertIn("neon.tech", database_url())
            self.assertIsNone(deployment_database_error())
            self.assertTrue(database_env_diagnostics()["has_remote_url"])

    def test_no_db_vars_on_vercel(self):
        env = {"VERCEL": "1", "VERCEL_ENV": "production"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(database_url(), "")
            err = deployment_database_error()
            self.assertIsNotNone(err)
            self.assertIn("Connect Project", err)


if __name__ == "__main__":
    unittest.main()
