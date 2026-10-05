"""Signed, stateless OAuth CSRF tokens (works on Vercel serverless without shared SQLite)."""

from __future__ import annotations

import os
from typing import Any

from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer

DEFAULT_MAX_AGE_SECONDS = 900


def _secret_key() -> str:
    key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if not key:
        key = "dev-change-me-in-production"
    return key


def _serializer(*, salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret_key(), salt=salt)


def issue_signed_state(
    *,
    salt: str,
    payload: dict[str, Any],
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> str:
    """Return an opaque state token embedding ``payload`` (max_age checked on load)."""
    del max_age_seconds  # enforced in loads_signed_state
    return _serializer(salt=salt).dumps(payload)


def loads_signed_state(
    *,
    salt: str,
    token: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        data = _serializer(salt=salt).loads(token, max_age=max_age_seconds)
    except (BadSignature, BadTimeSignature):
        return None
    if not isinstance(data, dict):
        return None
    return data
