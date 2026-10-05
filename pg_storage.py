"""Production storage status (PostgreSQL via DATABASE_URL)."""

from __future__ import annotations

import os

from app_config import is_vercel_runtime
from db_connection import database_url


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def postgres_configured() -> bool:
    return bool(database_url())


def ephemeral_local_storage() -> bool:
    """True when the app has no DATABASE_URL (e.g. misconfigured Vercel deploy)."""
    if postgres_configured():
        return False
    return is_vercel_runtime() or _env_bool("EPHEMERAL_STORAGE")


def should_trust_session_membership() -> bool:
    if _env_bool("AUTH_TRUST_SESSION_MEMBERSHIP"):
        return True
    if _env_bool("AUTH_STRICT_MEMBERSHIP"):
        return False
    return ephemeral_local_storage()


def storage_banner_for_ui() -> dict[str, str] | None:
    if postgres_configured():
        return None
    if not is_vercel_runtime() and not _env_bool("EPHEMERAL_STORAGE"):
        return {
            "message": "DATABASE_URL is not set — the app cannot save businesses or chats.",
            "detail": (
                "Set DATABASE_URL to postgresql://user:password@host:5432/dbname in your "
                "environment (see .env.example)."
            ),
        }
    return {
        "message": "Database is not configured — nothing you add will be saved.",
        "detail": (
            "Set DATABASE_URL on Vercel to your PostgreSQL connection string "
            "(Vercel Postgres, Neon, Supabase, etc.), then redeploy."
        ),
    }
