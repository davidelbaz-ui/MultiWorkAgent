"""Editable marketing / page copy (admin console)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app_db import connect, init_app_database

SECTION_META: dict[str, dict[str, str]] = {
    "start": {
        "title": "Marketing start page",
        "description": "Public landing page for visitors who are not signed in.",
    },
    "auth": {
        "title": "Sign in & sign up",
        "description": "Copy on authentication screens (not operator /admin login).",
    },
    "support": {
        "title": "Contact support",
        "description": "In-app support chat intro shown from Settings.",
    },
    "maintenance": {
        "title": "Maintenance mode",
        "description": "When enabled, customers see a maintenance page instead of the app.",
    },
}

SECTION_ORDER = ("start", "auth", "support", "maintenance")

PAGE_DEFINITIONS: list[dict[str, str]] = [
    {
        "key": "page.start.eyebrow",
        "label": "Eyebrow",
        "section": "start",
        "field": "text",
        "help": "Small label above the main headline.",
        "default": "Multi-business operations agent",
    },
    {
        "key": "page.start.hero_title",
        "label": "Hero headline",
        "section": "start",
        "field": "text",
        "help": "Primary H1 on the start page.",
        "default": "One agent. Every business. One dashboard.",
    },
    {
        "key": "page.start.hero_lead",
        "label": "Hero paragraph",
        "section": "start",
        "field": "textarea",
        "help": "Supporting text under the headline.",
        "default": (
            "MultiWorkAgent is your control surface for running work across many companies—chat "
            "with an AI operator, connect integrations and databases per business, and meter every "
            "action in clear execution runs."
        ),
    },
    {
        "key": "page.start.cta_signup",
        "label": "Primary button label",
        "section": "start",
        "field": "text",
        "help": "Main call-to-action (links to sign up).",
        "default": "Sign up now",
    },
    {
        "key": "page.start.cta_signin",
        "label": "Secondary button label",
        "section": "start",
        "field": "text",
        "help": "Secondary action in the hero (links to sign in).",
        "default": "Sign in",
    },
    {
        "key": "page.start.hero_note",
        "label": "Note under buttons",
        "section": "start",
        "field": "text",
        "help": "Fine print below the hero actions.",
        "default": "Starter plans from $19/mo · Scoped credentials · No shared secrets across businesses",
    },
    {
        "key": "page.auth.login_subtitle",
        "label": "Sign-in subtitle",
        "section": "auth",
        "field": "textarea",
        "help": "Shown under “Sign in” on the login page.",
        "default": "Sign in with Google, or use your email and password.",
    },
    {
        "key": "page.auth.signup_subtitle",
        "label": "Sign-up subtitle",
        "section": "auth",
        "field": "textarea",
        "help": "Shown under “Create account” on the sign-up page.",
        "default": "Create your workspace to manage businesses and connect integrations.",
    },
    {
        "key": "page.support.intro",
        "label": "Support intro",
        "section": "support",
        "field": "textarea",
        "help": "Paragraph under the Contact support heading. SLA hours still come from app config.",
        "default": (
            "Chat with our team. We aim to respond within 48 hours on business days. "
            "Your conversation is saved to your account so you can return anytime."
        ),
    },
    {
        "key": "page.support.banner",
        "label": "Support banner (legacy)",
        "section": "support",
        "field": "text",
        "help": "Optional short banner text if wired in templates.",
        "default": "We typically reply within 48 hours on business days.",
    },
    {
        "key": "page.maintenance.enabled",
        "label": "Enable maintenance mode",
        "section": "maintenance",
        "field": "toggle",
        "help": "Blocks the customer app until turned off.",
        "default": "0",
    },
    {
        "key": "page.maintenance.message",
        "label": "Maintenance message",
        "section": "maintenance",
        "field": "textarea",
        "help": "Shown to customers while maintenance mode is on.",
        "default": "MultiWorkAgent is undergoing maintenance. Please try again shortly.",
    },
]

_DEFAULTS = {item["key"]: item["default"] for item in PAGE_DEFINITIONS}
_META_BY_KEY = {item["key"]: item for item in PAGE_DEFINITIONS}
_TOGGLE_KEYS = frozenset(item["key"] for item in PAGE_DEFINITIONS if item.get("field") == "toggle")


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
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT page_key, value, updated_at, updated_by
            FROM site_settings
            ORDER BY page_key
            """
        ).fetchall()
    stored = {str(row["page_key"]): row for row in rows}
    results: list[dict[str, Any]] = []
    for item in PAGE_DEFINITIONS:
        key = item["key"]
        row = stored.get(key)
        results.append(_field_row(item, row))
    return results


def _field_row(item: dict[str, str], row: Any | None) -> dict[str, Any]:
    key = item["key"]
    if row:
        return {
            "key": key,
            "label": item["label"],
            "section": item.get("section", "other"),
            "field": item.get("field", "text"),
            "help": item.get("help", ""),
            "value": str(row["value"]),
            "default": item["default"],
            "updated_at": row["updated_at"],
            "updated_by": row["updated_by"],
        }
    return {
        "key": key,
        "label": item["label"],
        "section": item.get("section", "other"),
        "field": item.get("field", "text"),
        "help": item.get("help", ""),
        "value": item["default"],
        "default": item["default"],
        "updated_at": "",
        "updated_by": None,
    }


def admin_sections() -> list[dict[str, Any]]:
    by_key = {row["key"]: row for row in list_all()}
    sections: list[dict[str, Any]] = []
    for section_id in SECTION_ORDER:
        meta = SECTION_META.get(section_id, {"title": section_id, "description": ""})
        fields = [
            by_key[item["key"]]
            for item in PAGE_DEFINITIONS
            if item.get("section") == section_id and item["key"] in by_key
        ]
        if not fields:
            continue
        sections.append(
            {
                "id": section_id,
                "title": meta["title"],
                "description": meta.get("description", ""),
                "fields": fields,
            }
        )
    return sections


def update_values(values: dict[str, str], *, updated_by: str | None = None) -> None:
    allowed = set(_DEFAULTS)
    now = _utc_now()
    with connect() as conn:
        for key, raw in values.items():
            if key not in allowed:
                continue
            value = (raw or "").strip()
            if key in _TOGGLE_KEYS:
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


def apply_form_values(form: Any, *, updated_by: str | None = None) -> None:
    """Apply all known keys from an HTML form (handles unchecked toggles)."""
    values: dict[str, str] = {}
    for item in PAGE_DEFINITIONS:
        key = item["key"]
        if item.get("field") == "toggle":
            values[key] = "1" if form.get(key) == "1" else "0"
        elif key in form:
            values[key] = str(form.get(key) or "")
    update_values(values, updated_by=updated_by)


def maintenance_mode() -> tuple[bool, str]:
    enabled = get_value("page.maintenance.enabled", default="0").strip() in (
        "1",
        "true",
        "yes",
        "on",
    )
    message = get_value("page.maintenance.message")
    return enabled, message
