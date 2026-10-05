"""Contact support persistence (PostgreSQL, shared DATABASE_URL)."""

from __future__ import annotations

from db_connection import DBConnection, connect

__all__ = ["connect", "DBConnection"]
