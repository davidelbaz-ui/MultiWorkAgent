"""Read-only aggregates for the admin console."""

from __future__ import annotations

from typing import Any

from app_db import connect, expected_app_schema_version, get_app_schema_version
from db_connection import database_env_diagnostics, database_url


def database_status() -> dict[str, Any]:
    url = database_url()
    host = "not configured"
    if url:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "unknown") or "unknown"
    return {
        "configured": bool(url),
        "host": host,
        "schema_version": get_app_schema_version(),
        "expected_schema_version": expected_app_schema_version(),
        "env": database_env_diagnostics(),
    }


def platform_counts() -> dict[str, int]:
    with connect() as conn:
        accounts = conn.execute("SELECT COUNT(*) AS n FROM accounts").fetchone()
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        businesses = conn.execute("SELECT COUNT(*) AS n FROM businesses").fetchone()
        threads = conn.execute("SELECT COUNT(*) AS n FROM support_threads").fetchone()
        open_threads = conn.execute(
            "SELECT COUNT(*) AS n FROM support_threads WHERE status = 'open'"
        ).fetchone()
        runs = conn.execute("SELECT COUNT(*) AS n FROM agent_runs").fetchone()
    return {
        "accounts": int(accounts["n"]) if accounts else 0,
        "users": int(users["n"]) if users else 0,
        "businesses": int(businesses["n"]) if businesses else 0,
        "support_threads": int(threads["n"]) if threads else 0,
        "support_open": int(open_threads["n"]) if open_threads else 0,
        "agent_runs": int(runs["n"]) if runs else 0,
    }
