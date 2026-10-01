"""Canonical public URL helpers (Vercel production URL, reverse proxy)."""

from __future__ import annotations

import os

from flask import url_for

# Register this host in every OAuth provider console (login + integrations).
PRODUCTION_APP_BASE_URL = "https://multiworkagent.vercel.app"


def app_base_url() -> str | None:
    raw = os.environ.get("APP_BASE_URL", "").strip()
    if not raw:
        return None
    return raw.rstrip("/")


def login_oauth_callback_url(provider: str) -> str:
    """OAuth redirect URI sent to Google / Microsoft (must match provider console)."""
    base = app_base_url()
    if base:
        return f"{base}/auth/{provider}/callback"
    return url_for("login_oauth_callback", provider=provider, _external=True)


def integration_oauth_callback_url() -> str:
    """Redirect URI for third-party integration OAuth (must match provider console)."""
    base = app_base_url()
    if base:
        return f"{base}/integrations/oauth/callback"
    return url_for("integrations_oauth_callback", _external=True)
