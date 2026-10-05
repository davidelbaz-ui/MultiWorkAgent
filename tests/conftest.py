"""Shared PostgreSQL setup for tests."""

from __future__ import annotations

import os

import pytest

from db_connection import connect, database_url, require_database_url


def pytest_configure(config: pytest.Config) -> None:
    url = os.environ.get("TEST_DATABASE_URL", "").strip() or os.environ.get(
        "DATABASE_URL", ""
    ).strip()
    if not url:
        url = "postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent_test"
    os.environ["DATABASE_URL"] = url
    try:
        require_database_url()
        with connect() as conn:
            conn.execute("SELECT 1")
    except Exception as exc:
        pytest.exit(
            f"PostgreSQL required for tests. Set TEST_DATABASE_URL or start Postgres. ({exc})",
            returncode=1,
        )


@pytest.fixture(autouse=True)
def _clean_database() -> None:
    from tests.db_test_utils import reset_public_schema

    reset_public_schema()
    yield
    reset_public_schema()
