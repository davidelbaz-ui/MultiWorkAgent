"""Simplified test setUp helpers — PostgreSQL is configured in conftest.py."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

import auth_store


class PostgresStoreTestCase(unittest.TestCase):
    """Base case: DB is reset before each test via conftest."""

    def setUp(self) -> None:
        auth_store.bootstrap()


class TempDirTestCase(PostgresStoreTestCase):
    _tmpdir: tempfile.TemporaryDirectory

    def setUp(self) -> None:
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        gc.collect()
        try:
            self._tmpdir.cleanup()
        except PermissionError:
            pass
        super().tearDown()
