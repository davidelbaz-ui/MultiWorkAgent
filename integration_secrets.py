"""Encrypt integration credentials at rest (Fernet, key from env)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    raw = os.environ.get("INTEGRATION_ENCRYPTION_KEY") or os.environ.get(
        "FLASK_SECRET_KEY",
        "dev-change-me-in-production",
    )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_credentials(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(data).decode("ascii")


def decrypt_credentials(token: str) -> dict[str, Any]:
    try:
        raw = _fernet().decrypt(token.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("invalid credential blob") from exc
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("credential payload must be an object")
    return parsed


def credential_hint(api_key: str) -> str:
    clean = api_key.strip()
    if len(clean) <= 4:
        return "****"
    return f"{clean[:3]}…{clean[-4:]}"
