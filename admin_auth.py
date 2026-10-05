"""Operator login for /admin (separate from customer accounts)."""

from __future__ import annotations

import os
import secrets

from werkzeug.security import check_password_hash

from auth_store import normalize_email, validate_email


def admin_email() -> str | None:
    raw = os.environ.get("ADMIN_EMAIL", "").strip()
    return validate_email(raw)


def admin_configured() -> bool:
    email = admin_email()
    if not email:
        return False
    if os.environ.get("ADMIN_PASSWORD_HASH", "").strip():
        return True
    return bool(os.environ.get("ADMIN_PASSWORD", "").strip())


def verify_admin_login(email: str, password: str) -> bool:
    expected_email = admin_email()
    if not expected_email or not admin_configured():
        return False
    if normalize_email(email) != expected_email:
        return False
    if not isinstance(password, str) or not password:
        return False
    hashed = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
    if hashed:
        return check_password_hash(hashed, password)
    plain = os.environ.get("ADMIN_PASSWORD", "").strip()
    return bool(plain) and secrets.compare_digest(plain, password)
