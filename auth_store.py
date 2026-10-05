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


def _format_timestamp(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    except ValueError:
        return iso


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
            SELECT id, email, display_name, created_at, last_login_at
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


def touch_last_login(user_id: str) -> None:
    """Persist UTC timestamp when a customer completes sign-in."""
    if not user_id:
        return
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (now, user_id),
        )
        conn.commit()


def list_users_for_admin(
    *,
    query: str = "",
    role: str = "",
    sign_in: str = "",
    last_login: str = "",
    sort: str = "created_desc",
) -> tuple[list[dict[str, Any]], int]:
    """Return filtered user rows for admin and total matching count."""
    from datetime import timedelta

    conditions: list[str] = []
    params: list[Any] = []

    clean_query = query.strip().lower()
    if clean_query:
        like = f"%{clean_query}%"
        conditions.append(
            "(LOWER(u.email) LIKE ? OR LOWER(COALESCE(u.display_name, '')) LIKE ?)"
        )
        params.extend([like, like])

    if role in ROLES:
        conditions.append("m.role = ?")
        params.append(role)

    if sign_in == "password":
        conditions.append(
            "NOT EXISTS (SELECT 1 FROM user_auth_identities i WHERE i.user_id = u.id)"
        )
    elif sign_in == "oauth":
        conditions.append(
            "EXISTS (SELECT 1 FROM user_auth_identities i WHERE i.user_id = u.id)"
        )
    elif sign_in in OAUTH_PROVIDERS:
        conditions.append(
            "EXISTS (SELECT 1 FROM user_auth_identities i WHERE i.user_id = u.id AND i.provider = ?)"
        )
        params.append(sign_in)

    if last_login == "never":
        conditions.append("u.last_login_at IS NULL")
    elif last_login in {"7d", "30d"}:
        days = 7 if last_login == "7d" else 30
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=days)
        ).replace(microsecond=0).isoformat()
        conditions.append("u.last_login_at >= ?")
        params.append(cutoff)

    where_sql = " AND ".join(conditions) if conditions else "TRUE"

    sort_sql = {
        "name_asc": "LOWER(COALESCE(NULLIF(TRIM(u.display_name), ''), u.email)) ASC, u.email ASC",
        "name_desc": "LOWER(COALESCE(NULLIF(TRIM(u.display_name), ''), u.email)) DESC, u.email DESC",
        "email_asc": "LOWER(u.email) ASC",
        "email_desc": "LOWER(u.email) DESC",
        "created_asc": "u.created_at ASC",
        "created_desc": "u.created_at DESC",
        "account_asc": "a.created_at ASC NULLS LAST",
        "account_desc": "a.created_at DESC NULLS LAST",
        "last_login_asc": "u.last_login_at ASC NULLS LAST",
        "last_login_desc": "u.last_login_at DESC NULLS LAST",
        "businesses_asc": "business_count ASC",
        "businesses_desc": "business_count DESC",
    }.get(sort, "u.created_at DESC")

    base_from = """
            FROM users u
            LEFT JOIN account_members m ON m.user_id = u.id
            LEFT JOIN accounts a ON a.id = m.account_id
            """

    with connect() as conn:
        count_row = conn.execute(
            f"SELECT COUNT(*) AS n {base_from} WHERE {where_sql}",
            tuple(params),
        ).fetchone()
        total = int(count_row["n"]) if count_row else 0

        rows = conn.execute(
            f"""
            SELECT
                u.id,
                u.email,
                u.display_name,
                u.created_at,
                u.last_login_at,
                m.role,
                m.created_at AS member_since,
                a.id AS account_id,
                a.created_at AS account_created_at,
                (
                    SELECT COUNT(*)
                    FROM businesses b
                    WHERE b.account_id = a.id
                      AND b.archived_at IS NULL
                ) AS business_count,
                (
                    SELECT string_agg(i.provider, ', ' ORDER BY i.provider)
                    FROM user_auth_identities i
                    WHERE i.user_id = u.id
                ) AS oauth_providers
            {base_from}
            WHERE {where_sql}
            ORDER BY {sort_sql}
            """,
            tuple(params),
        ).fetchall()
    users: list[dict[str, Any]] = []
    for row in rows:
        name = (row["display_name"] or "").strip() or row["email"]
        oauth = (row["oauth_providers"] or "").strip()
        sign_in: list[str] = []
        if oauth:
            for part in oauth.split(", "):
                label = part.strip().capitalize()
                if label:
                    sign_in.append(label)
        sign_in.append("Password")
        users.append(
            {
                "id": row["id"],
                "name": name,
                "email": row["email"],
                "display_name": (row["display_name"] or "").strip(),
                "created_at": row["created_at"],
                "created_at_display": _format_timestamp(row["created_at"]),
                "last_login_at": row["last_login_at"],
                "last_login_display": _format_timestamp(row["last_login_at"]),
                "role": row["role"],
                "role_label": ROLE_LABELS.get(row["role"], row["role"])
                if row["role"]
                else "",
                "account_id": row["account_id"],
                "account_created_at": row["account_created_at"],
                "account_created_display": _format_timestamp(row["account_created_at"]),
                "member_since": row["member_since"],
                "member_since_display": _format_timestamp(row["member_since"]),
                "business_count": int(row["business_count"] or 0),
                "sign_in_methods": ", ".join(sign_in),
            }
        )
    return users, total


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
    keys = row.keys() if hasattr(row, "keys") else ()
    last_login = row["last_login_at"] if "last_login_at" in keys else None
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": name,
        "name": name or row["email"],
        "created_at": row["created_at"],
        "last_login_at": last_login,
    }
