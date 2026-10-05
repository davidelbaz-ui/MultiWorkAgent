"""Editable marketing / page copy (admin console)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app_db import connect, init_app_database

PAGE_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "page.start.hero_title",
        "label": "Start page — hero title",
        "default": "One agent. Every business. One dashboard.",
    },
    {
        "key": "page.start.hero_lead",
        "label": "Start page — hero paragraph",
        "default": (
            "MultiWorkAgent is your control surface for running work across many companies—chat "
            "with an AI operator, connect integrations and databases per business, and meter every "
            "action in clear execution runs."
        ),
    },
    {
        "key": "page.start.hero_note",
        "label": "Start page — note under buttons",
        "default": "Starter plans from $19/mo · Scoped credentials · No shared secrets across businesses",
    },
    {
        "key": "page.support.banner",
        "label": "Contact support — intro banner",
        "default": "We typically reply within 48 hours on business days.",
    },
    {
        "key": "page.maintenance.enabled",
        "label": "Maintenance mode (1 = on, 0 = off)",
        "default": "0",
    },
    {
        "key": "page.maintenance.message",
        "label": "Maintenance message",
        "default": "MultiWorkAgent is undergoing maintenance. Please try again shortly.",
    },
]

_DEFAULTS = {item["key"]: item["default"] for item in PAGE_DEFINITIONS}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()
    now = _utc_now()
    with connect() as conn:
        for key, default in _DEFAULTS.items():
            conn.execute(
                """
                INSERT INTO site_settings (page_key, value, updated_at, updated_by)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(page_key) DO NOTHING
                """,
                (key, default, now),
            )
        conn.commit()


def get_value(page_key: str, *, default: str = "") -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT value FROM site_settings WHERE page_key = ?",
            (page_key,),
        ).fetchone()
    if not row:
        return _DEFAULTS.get(page_key, default)
    return str(row["value"])


def get_many(keys: list[str]) -> dict[str, str]:
    if not keys:
        return {}
    placeholders = ", ".join("?" for _ in keys)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT page_key, value FROM site_settings WHERE page_key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
    out = {key: _DEFAULTS.get(key, "") for key in keys}
    for row in rows:
        out[str(row["page_key"])] = str(row["value"])
    return out


def list_all() -> list[dict[str, Any]]:
    meta = {item["key"]: item for item in PAGE_DEFINITIONS}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT page_key, value, updated_at, updated_by
            FROM site_settings
            ORDER BY page_key
            """
        ).fetchall()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row["page_key"])
        seen.add(key)
        info = meta.get(key, {"label": key, "default": ""})
        results.append(
            {
                "key": key,
                "label": info.get("label", key),
                "value": str(row["value"]),
                "default": info.get("default", ""),
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by"],
            }
        )
    for item in PAGE_DEFINITIONS:
        if item["key"] not in seen:
            results.append(
                {
                    "key": item["key"],
                    "label": item["label"],
                    "value": item["default"],
                    "default": item["default"],
                    "updated_at": "",
                    "updated_by": None,
                }
            )
    return sorted(results, key=lambda r: r["key"])


def update_values(values: dict[str, str], *, updated_by: str | None = None) -> None:
    allowed = set(_DEFAULTS)
    now = _utc_now()
    with connect() as conn:
        for key, raw in values.items():
            if key not in allowed:
                continue
            value = (raw or "").strip()
            if key == "page.maintenance.enabled":
                value = "1" if value in ("1", "true", "on", "yes") else "0"
            conn.execute(
                """
                INSERT INTO site_settings (page_key, value, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(page_key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (key, value, now, updated_by),
            )
        conn.commit()


def maintenance_mode() -> tuple[bool, str]:
    enabled = get_value("page.maintenance.enabled", default="0").strip() in (
        "1",
        "true",
        "yes",
        "on",
    )
    message = get_value("page.maintenance.message")
    return enabled, message
