"""Team invitations to join an account workspace."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import auth_store
import business_store
import user_notification_store
from app_db import connect, init_app_database

INVITE_ROLES = frozenset({"operator", "viewer"})
STATUSES = frozenset({"pending", "accepted", "declined", "cancelled"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def _row_to_invite(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "invitee_email": row["invitee_email"],
        "invitee_user_id": row["invitee_user_id"],
        "role": row["role"],
        "role_label": auth_store.ROLE_LABELS.get(row["role"], row["role"]),
        "invited_by_user_id": row["invited_by_user_id"],
        "status": row["status"],
        "user_notification_id": row["user_notification_id"],
        "created_at": row["created_at"],
        "responded_at": row["responded_at"],
    }


def get_invite(invite_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, invitee_email, invitee_user_id, role,
                   invited_by_user_id, status, user_notification_id, created_at, responded_at
            FROM account_team_invites
            WHERE id = ?
            """,
            (invite_id,),
        ).fetchone()
    return _row_to_invite(row) if row else None


def list_pending_for_account(account_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, account_id, invitee_email, invitee_user_id, role,
                   invited_by_user_id, status, user_notification_id, created_at, responded_at
            FROM account_team_invites
            WHERE account_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (account_id,),
        ).fetchall()
    return [_row_to_invite(row) for row in rows]


def _pending_for_email(account_id: str, email: str) -> dict[str, Any] | None:
    clean = auth_store.validate_email(email)
    if not clean:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, account_id, invitee_email, invitee_user_id, role,
                   invited_by_user_id, status, user_notification_id, created_at, responded_at
            FROM account_team_invites
            WHERE account_id = ? AND invitee_email = ? AND status = 'pending'
            LIMIT 1
            """,
            (account_id, clean),
        ).fetchone()
    return _row_to_invite(row) if row else None


def _account_display_name(account_id: str) -> str:
    owner = auth_store.list_account_members(account_id)
    owner_row = next((m for m in owner if m["role"] == "owner"), owner[0] if owner else None)
    if owner_row:
        return f"{owner_row['name']}'s workspace"
    return "MultiWorkAgent workspace"


def _notify_invitee(invite: dict[str, Any]) -> str | None:
    user_id = invite.get("invitee_user_id")
    if not user_id:
        return None
    workspace = _account_display_name(invite["account_id"])
    role_label = invite.get("role_label") or invite["role"]
    note = user_notification_store.create_notification(
        user_id,
        kind="team_invite",
        title="Team invitation",
        body=f"You were invited to join {workspace} as {role_label}.",
        href="/settings",
        invite_id=invite["id"],
        dedupe_key=f"team_invite:{invite['id']}",
    )
    return note.get("id")


def sync_invites_for_user(user_id: str, email: str) -> int:
    """Attach pending email invites to a user and create notifications."""
    clean = auth_store.validate_email(email)
    if not clean:
        return 0
    updated = 0
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, account_id, invitee_email, invitee_user_id, role,
                   invited_by_user_id, status, user_notification_id, created_at, responded_at
            FROM account_team_invites
            WHERE invitee_email = ? AND status = 'pending'
              AND (invitee_user_id IS NULL OR invitee_user_id = ?)
            """,
            (clean, user_id),
        ).fetchall()
    for row in rows:
        invite = _row_to_invite(row)
        if auth_store.get_membership(invite["account_id"], user_id):
            _set_status(invite["id"], "cancelled")
            continue
        with connect() as conn:
            conn.execute(
                """
                UPDATE account_team_invites
                SET invitee_user_id = ?
                WHERE id = ? AND status = 'pending'
                """,
                (user_id, invite["id"]),
            )
            conn.commit()
        invite["invitee_user_id"] = user_id
        if not invite.get("user_notification_id"):
            nid = _notify_invitee(invite)
            if nid:
                with connect() as conn:
                    conn.execute(
                        """
                        UPDATE account_team_invites SET user_notification_id = ?
                        WHERE id = ?
                        """,
                        (nid, invite["id"]),
                    )
                    conn.commit()
        updated += 1
    return updated


def create_invite(
    account_id: str,
    *,
    email: str,
    role: str,
    invited_by_user_id: str,
) -> dict[str, Any]:
    business_store.ensure_account(account_id)
    clean_email = auth_store.validate_email(email)
    if not clean_email:
        raise ValueError("Enter a valid email address.")
    role = role.strip().lower()
    if role not in INVITE_ROLES:
        raise ValueError("Role must be operator or viewer.")

    inviter = auth_store.get_membership(account_id, invited_by_user_id)
    if not inviter or inviter["role"] != "owner":
        raise PermissionError("Only the account owner can invite teammates.")

    existing_user = auth_store.get_user_by_email(clean_email)
    if existing_user:
        if auth_store.get_membership(account_id, existing_user["id"]):
            raise ValueError("That person is already on this team.")
        inviter_user = auth_store.get_user(invited_by_user_id)
        if inviter_user and auth_store.normalize_email(inviter_user["email"]) == clean_email:
            raise ValueError("You cannot invite yourself.")

    if _pending_for_email(account_id, clean_email):
        raise ValueError("A pending invite already exists for that email.")

    invite_id = str(uuid.uuid4())
    now = _utc_now()
    invitee_user_id = existing_user["id"] if existing_user else None
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO account_team_invites (
                id, account_id, invitee_email, invitee_user_id, role,
                invited_by_user_id, status, user_notification_id, created_at, responded_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, ?, NULL)
            """,
            (
                invite_id,
                account_id,
                clean_email,
                invitee_user_id,
                role,
                invited_by_user_id,
                now,
            ),
        )
        conn.commit()

    invite = get_invite(invite_id)
    if not invite:
        raise RuntimeError("failed to create invite")

    if invitee_user_id:
        nid = _notify_invitee(invite)
        if nid:
            with connect() as conn:
                conn.execute(
                    "UPDATE account_team_invites SET user_notification_id = ? WHERE id = ?",
                    (nid, invite_id),
                )
                conn.commit()
            invite = get_invite(invite_id) or invite

    return invite


def cancel_invite(account_id: str, invite_id: str, *, actor_user_id: str) -> bool:
    inviter = auth_store.get_membership(account_id, actor_user_id)
    if not inviter or inviter["role"] != "owner":
        raise PermissionError("Only the account owner can cancel invites.")
    invite = get_invite(invite_id)
    if not invite or invite["account_id"] != account_id or invite["status"] != "pending":
        return False
    _set_status(invite_id, "cancelled")
    uid = invite.get("invitee_user_id")
    nid = invite.get("user_notification_id")
    if uid and nid:
        user_notification_store.delete_notification(uid, nid)
    return True


def _set_status(invite_id: str, status: str) -> None:
    if status not in STATUSES:
        raise ValueError("invalid status")
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE account_team_invites
            SET status = ?, responded_at = ?
            WHERE id = ?
            """,
            (status, now, invite_id),
        )
        conn.commit()


def accept_invite(invite_id: str, *, user_id: str) -> dict[str, Any]:
    invite = get_invite(invite_id)
    if not invite or invite["status"] != "pending":
        raise ValueError("This invitation is no longer available.")
    user = auth_store.get_user(user_id)
    if not user:
        raise ValueError("User not found.")
    if auth_store.normalize_email(user["email"]) != invite["invitee_email"]:
        raise PermissionError("This invitation was sent to a different email address.")
    if auth_store.get_membership(invite["account_id"], user_id):
        _set_status(invite_id, "accepted")
        raise ValueError("You are already on this team.")

    membership = auth_store.add_account_member(
        invite["account_id"],
        user_id,
        invite["role"],
    )
    _set_status(invite_id, "accepted")
    nid = invite.get("user_notification_id")
    if nid:
        user_notification_store.mark_read(user_id, nid)
    return {"invite": get_invite(invite_id) or invite, "membership": membership}


def decline_invite(invite_id: str, *, user_id: str) -> bool:
    invite = get_invite(invite_id)
    if not invite or invite["status"] != "pending":
        return False
    user = auth_store.get_user(user_id)
    if not user or auth_store.normalize_email(user["email"]) != invite["invitee_email"]:
        raise PermissionError("This invitation was sent to a different email address.")
    _set_status(invite_id, "declined")
    nid = invite.get("user_notification_id")
    if nid:
        user_notification_store.delete_notification(user_id, nid)
    return True
