"""Canonical public URL helpers (Vercel production URL, reverse proxy)."""

from __future__ import annotations

import os

from flask import url_for

# Register this host in every OAuth provider console (login + integrations).
PRODUCTION_APP_BASE_URL = "https://multiworkagent.vercel.app"


def _normalize_public_base_url(raw: str) -> str:
    base = raw.strip().rstrip("/")
    if not base:
        return base
    on_vercel = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))
    if base.startswith("http://") and (
        on_vercel or base.endswith(".vercel.app") or "multiworkagent" in base
    ):
        base = "https://" + base[len("http://") :]
    return base


def app_base_url() -> str | None:
    raw = os.environ.get("APP_BASE_URL", "").strip()
    if raw:
        return _normalize_public_base_url(raw)
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        return PRODUCTION_APP_BASE_URL.rstrip("/")
    return None


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


def public_app_base_url() -> str:
    """Customer-facing site URL for links in operator tools."""
    return app_base_url() or "http://127.0.0.1:5000"


def billing_checkout_return_url() -> str:
    """Square redirect after subscription checkout (must match payment link config)."""
    base = app_base_url()
    path = url_for("billing", checkout="done", _external=False)
    if base:
        return f"{base}{path}"
    return url_for("billing", checkout="done", _external=True)


def square_webhook_notification_url() -> str:
    """URL registered in Square Developer → Webhooks (used for signature verification)."""
    base = app_base_url()
    if base:
        return f"{base}/webhooks/square"
    return url_for("square_webhook", _external=True)
