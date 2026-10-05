"""Truncate PostgreSQL between tests."""

from __future__ import annotations

import app_db
from app_migrations import run_migrations
from db_connection import connect


def reset_public_schema() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename NOT LIKE 'pg_%'
            """
        ).fetchall()
        if rows:
            names = ", ".join(f'"{row["tablename"]}"' for row in rows)
            conn.execute(f"TRUNCATE {names} RESTART IDENTITY CASCADE")
        run_migrations(conn)
