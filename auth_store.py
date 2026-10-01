"""Account users, credentials, and team membership."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from app_db import connect, init_app_database

ROLES = frozenset({"owner", "operator", "viewer"})
ROLE_LABELS = {
    "owner": "Owner",
    "operator": "Operator",
    "viewer": "Viewer",
}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MIN_PASSWORD_LEN = 8
OAUTH_PROVIDERS = frozenset({"google", "microsoft"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> str | None:
    clean = normalize_email(email)
    if not clean or not _EMAIL_RE.match(clean):
        return None
    return clean


def validate_password(password: str) -> str | None:
    if not isinstance(password, str) or len(password) < _MIN_PASSWORD_LEN:
        return None
    return password


def get_user(user_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, display_name, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    clean = validate_email(email)
    if not clean:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, password_hash, display_name, created_at
            FROM users
            WHERE email = ?
            """,
            (clean,),
        ).fetchone()
    if not row:
        return None
    user = _row_to_user(row)
    user["password_hash"] = row["password_hash"]
    return user


def get_membership(account_id: str, user_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT account_id, user_id, role, created_at
            FROM account_members
            WHERE account_id = ? AND user_id = ?
            """,
            (account_id, user_id),
        ).fetchone()
    if not row:
        return None
    return {
        "account_id": row["account_id"],
        "user_id": row["user_id"],
        "role": row["role"],
        "role_label": ROLE_LABELS.get(row["role"], row["role"]),
        "created_at": row["created_at"],
    }


def get_primary_membership(user_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT account_id, user_id, role, created_at
            FROM account_members
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return get_membership(row["account_id"], row["user_id"])


def list_account_members(account_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.email, u.display_name, m.role
            FROM account_members m
            JOIN users u ON u.id = m.user_id
            WHERE m.account_id = ?
            ORDER BY
                CASE m.role
                    WHEN 'owner' THEN 0
                    WHEN 'operator' THEN 1
                    ELSE 2
                END,
                u.display_name,
                u.email
            """,
            (account_id,),
        ).fetchall()
    members: list[dict[str, Any]] = []
    for row in rows:
        name = (row["display_name"] or "").strip() or row["email"]
        members.append(
            {
                "id": row["id"],
                "name": name,
                "email": row["email"],
                "role": row["role"],
                "role_label": ROLE_LABELS.get(row["role"], row["role"]),
            }
        )
    return members


def create_account_with_owner(
    *,
    email: str,
    password: str,
    display_name: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    clean_email = validate_email(email)
    if not clean_email:
        raise ValueError("Enter a valid email address")
    clean_password = validate_password(password)
    if not clean_password:
        raise ValueError(f"Password must be at least {_MIN_PASSWORD_LEN} characters")

    existing = get_user_by_email(clean_email)
    if existing:
        raise ValueError("An account with this email already exists")

    account_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    now = _utc_now()
    clean_name = display_name.strip()
    password_hash = generate_password_hash(clean_password)

    with connect() as conn:
        conn.execute(
            "INSERT INTO accounts (id, created_at) VALUES (?, ?)",
            (account_id, now),
        )
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, display_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, clean_email, password_hash, clean_name, now),
        )
        conn.execute(
            """
            INSERT INTO account_members (account_id, user_id, role, created_at)
            VALUES (?, ?, 'owner', ?)
            """,
            (account_id, user_id, now),
        )
        conn.commit()

    user = get_user(user_id)
    membership = get_membership(account_id, user_id)
    if not user or not membership:
        raise RuntimeError("failed to create account")
    return user, membership


def get_user_by_oauth_identity(provider: str, provider_subject: str) -> dict[str, Any] | None:
    if provider not in OAUTH_PROVIDERS or not provider_subject:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.display_name, u.created_at
            FROM user_auth_identities i
            JOIN users u ON u.id = i.user_id
            WHERE i.provider = ? AND i.provider_subject = ?
            """,
            (provider, provider_subject),
        ).fetchone()
    return _row_to_user(row) if row else None


def _insert_oauth_identity(
    conn,
    *,
    user_id: str,
    provider: str,
    provider_subject: str,
    email: str,
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO user_auth_identities (
            id, user_id, provider, provider_subject, email_at_link, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), user_id, provider, provider_subject, email, now),
    )


def link_oauth_identity(
    *,
    user_id: str,
    provider: str,
    provider_subject: str,
    email: str,
) -> None:
    if provider not in OAUTH_PROVIDERS:
        raise ValueError("Unsupported login provider")
    if not provider_subject:
        raise ValueError("Missing provider user id")
    clean_email = validate_email(email) or email.strip().lower()
    now = _utc_now()
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT user_id FROM user_auth_identities
            WHERE provider = ? AND provider_subject = ?
            """,
            (provider, provider_subject),
        ).fetchone()
        if existing:
            if existing["user_id"] != user_id:
                raise ValueError("This social account is linked to another user")
            return
        row = conn.execute(
            """
            SELECT 1 FROM user_auth_identities
            WHERE user_id = ? AND provider = ?
            """,
            (user_id, provider),
        ).fetchone()
        if row:
            raise ValueError(f"A {provider} account is already linked to this user")
        _insert_oauth_identity(
            conn,
            user_id=user_id,
            provider=provider,
            provider_subject=provider_subject,
            email=clean_email,
            now=now,
        )
        conn.commit()


def create_account_with_oauth(
    *,
    email: str,
    display_name: str,
    provider: str,
    provider_subject: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if provider not in OAUTH_PROVIDERS:
        raise ValueError("Unsupported login provider")
    clean_email = validate_email(email)
    if not clean_email:
        raise ValueError("Provider did not return a valid email")
    if not provider_subject:
        raise ValueError("Missing provider user id")

    existing_identity = get_user_by_oauth_identity(provider, provider_subject)
    if existing_identity:
        membership = get_primary_membership(existing_identity["id"])
        if membership:
            return existing_identity, membership
        raise RuntimeError("OAuth identity exists without membership")

    existing_user = get_user_by_email(clean_email)
    if existing_user:
        link_oauth_identity(
            user_id=existing_user["id"],
            provider=provider,
            provider_subject=provider_subject,
            email=clean_email,
        )
        membership = get_primary_membership(existing_user["id"])
        if not membership:
            raise RuntimeError("User exists without membership")
        user = get_user(existing_user["id"])
        if not user:
            raise RuntimeError("failed to load user")
        if display_name.strip() and not user.get("display_name"):
            _update_display_name(existing_user["id"], display_name.strip())
            user = get_user(existing_user["id"]) or user
        return user, membership

    account_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    now = _utc_now()
    clean_name = display_name.strip()
    password_hash = generate_password_hash(secrets.token_urlsafe(32))

    with connect() as conn:
        conn.execute(
            "INSERT INTO accounts (id, created_at) VALUES (?, ?)",
            (account_id, now),
        )
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, display_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, clean_email, password_hash, clean_name, now),
        )
        conn.execute(
            """
            INSERT INTO account_members (account_id, user_id, role, created_at)
            VALUES (?, ?, 'owner', ?)
            """,
            (account_id, user_id, now),
        )
        _insert_oauth_identity(
            conn,
            user_id=user_id,
            provider=provider,
            provider_subject=provider_subject,
            email=clean_email,
            now=now,
        )
        conn.commit()

    user = get_user(user_id)
    membership = get_membership(account_id, user_id)
    if not user or not membership:
        raise RuntimeError("failed to create account")
    return user, membership


def login_with_oauth_profile(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    provider = profile.get("provider") or ""
    subject = profile.get("subject") or ""
    email = profile.get("email") or ""
    display_name = profile.get("display_name") or ""
    if not profile.get("email_verified"):
        raise ValueError("Email address is not verified by the provider")

    user = get_user_by_oauth_identity(provider, subject)
    if user:
        membership = get_primary_membership(user["id"])
        if not membership:
            raise RuntimeError("User exists without membership")
        return user, membership

    return create_account_with_oauth(
        email=email,
        display_name=display_name,
        provider=provider,
        provider_subject=subject,
    )


def _update_display_name(user_id: str, display_name: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name, user_id),
        )
        conn.commit()


def authenticate(email: str, password: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    record = get_user_by_email(email)
    if not record:
        return None
    if not check_password_hash(record["password_hash"], password):
        return None
    membership = get_primary_membership(record["id"])
    if not membership:
        return None
    user = get_user(record["id"])
    if not user:
        return None
    return user, membership


def _row_to_user(row: Any) -> dict[str, Any]:
    name = (row["display_name"] or "").strip()
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": name,
        "name": name or row["email"],
        "created_at": row["created_at"],
    }
