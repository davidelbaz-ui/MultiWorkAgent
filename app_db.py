"""Primary PostgreSQL database for accounts, businesses, and app domain data."""

from __future__ import annotations

from app_migrations import APP_SCHEMA_VERSION, current_schema_version, run_migrations
from db_connection import DBConnection, connect, database_url, require_database_url


def init_app_database() -> None:
    require_database_url()
    with connect() as conn:
        run_migrations(conn)


def get_app_schema_version() -> int:
    if not database_url():
        return 0
    with connect() as conn:
        return current_schema_version(conn)


def expected_app_schema_version() -> int:
    return APP_SCHEMA_VERSION


__all__ = ["connect", "init_app_database", "get_app_schema_version", "expected_app_schema_version"]
