"""Per-user settings (appearance, agent behavior) scoped to an account membership."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import auth_store
import notification_store
from app_db import connect, init_app_database

THEME_VALUES = frozenset({"light", "dark", "device"})
DEFAULT_AUTO_APPROVE_MAX_UNITS = 0.25


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def ensure_user_settings(user_id: str, account_id: str) -> None:
    if not auth_store.get_membership(account_id, user_id):
        raise LookupError("membership not found")
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_settings (
                user_id, account_id, theme, agent_auto_approve_enabled,
                agent_auto_approve_max_run_units, agent_prompt_caching_enabled,
                created_at, updated_at
            ) VALUES (?, ?, 'device', 1, ?, 1, ?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (
                user_id,
                account_id,
                DEFAULT_AUTO_APPROVE_MAX_UNITS,
                now,
                now,
            ),
        )
        conn.commit()


def _row_to_settings(row: Any) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "account_id": row["account_id"],
        "theme": row["theme"],
        "agent_auto_approve_enabled": bool(row["agent_auto_approve_enabled"]),
        "agent_auto_approve_max_run_units": float(row["agent_auto_approve_max_run_units"]),
        "agent_prompt_caching_enabled": bool(row["agent_prompt_caching_enabled"]),
        "updated_at": row["updated_at"],
    }


def get_user_settings(user_id: str, account_id: str) -> dict[str, Any]:
    ensure_user_settings(user_id, account_id)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                user_id, account_id, theme, agent_auto_approve_enabled,
                agent_auto_approve_max_run_units, agent_prompt_caching_enabled,
                updated_at
            FROM user_settings
            WHERE user_id = ? AND account_id = ?
            """,
            (user_id, account_id),
        ).fetchone()
    if not row:
        raise RuntimeError("user settings missing")
    return _row_to_settings(row)


def update_user_settings(user_id: str, account_id: str, **kwargs: Any) -> dict[str, Any]:
    ensure_user_settings(user_id, account_id)
    updates: dict[str, Any] = {}
    if "theme" in kwargs:
        theme = str(kwargs["theme"]).strip().lower()
        if theme not in THEME_VALUES:
            raise ValueError("theme must be light, dark, or device")
        updates["theme"] = theme
    if "agent_auto_approve_enabled" in kwargs:
        updates["agent_auto_approve_enabled"] = 1 if kwargs["agent_auto_approve_enabled"] else 0
    if "agent_auto_approve_max_run_units" in kwargs:
        value = float(kwargs["agent_auto_approve_max_run_units"])
        if value < 0 or value > 1:
            raise ValueError("agent_auto_approve_max_run_units must be between 0 and 1")
        updates["agent_auto_approve_max_run_units"] = value
    if "agent_prompt_caching_enabled" in kwargs:
        updates["agent_prompt_caching_enabled"] = (
            1 if kwargs["agent_prompt_caching_enabled"] else 0
        )

    if not updates:
        return get_user_settings(user_id, account_id)

    now = _utc_now()
    sets = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values()) + [now, user_id, account_id]
    with connect() as conn:
        conn.execute(
            f"""
            UPDATE user_settings
            SET {sets}, updated_at = ?
            WHERE user_id = ? AND account_id = ?
            """,
            params,
        )
        conn.commit()
    return get_user_settings(user_id, account_id)


def appearance_to_api(settings: dict[str, Any]) -> dict[str, Any]:
    return {"theme": settings["theme"]}


def agent_to_api(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "auto_approve_enabled": settings["agent_auto_approve_enabled"],
        "auto_approve_max_run_units": settings["agent_auto_approve_max_run_units"],
        "prompt_caching_enabled": settings["agent_prompt_caching_enabled"],
    }


def settings_bundle(user_id: str, account_id: str) -> dict[str, Any]:
    user = get_user_settings(user_id, account_id)
    prefs = notification_store.ensure_prefs(account_id)
    notifications = {key: prefs[key] for key in notification_store.PREF_KEYS}
    return {
        "appearance": appearance_to_api(user),
        "agent": agent_to_api(user),
        "notifications": notifications,
    }


def should_auto_approve_run(user_id: str, account_id: str, estimated_run_units: float) -> bool:
    """Used by agent confirmation flow when wired."""
    settings = get_user_settings(user_id, account_id)
    if not settings["agent_auto_approve_enabled"]:
        return False
    cap = settings["agent_auto_approve_max_run_units"]
    return estimated_run_units <= cap
