"""Account deletion and operational data purge."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import chat_store
import support_store
from app_db import connect, init_app_database


class AccountLifecycleError(Exception):
    def __init__(self, message: str, *, code: str = "forbidden") -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def remember_chat_workspace(account_id: str, *, scope_key: str, workspace_id: str) -> None:
    if not account_id or not workspace_id:
        return
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO account_chat_workspaces (account_id, scope_key, workspace_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(account_id, scope_key) DO UPDATE SET
                workspace_id = excluded.workspace_id,
                created_at = excluded.created_at
            """,
            (account_id, scope_key or "default", workspace_id, now),
        )
        conn.commit()


def list_chat_workspace_ids(account_id: str) -> list[str]:
    ids: set[str] = set()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT workspace_id FROM account_chat_workspaces
            WHERE account_id = ?
            """,
            (account_id,),
        ).fetchall()
        for row in rows:
            if row["workspace_id"]:
                ids.add(row["workspace_id"])
        run_rows = conn.execute(
            """
            SELECT DISTINCT thread_id FROM agent_runs
            WHERE account_id = ? AND thread_id IS NOT NULL AND thread_id != ''
            """,
            (account_id,),
        ).fetchall()
    for row in run_rows:
        thread_id = row["thread_id"]
        meta = chat_store.get_thread_meta(thread_id)
        if meta and meta.get("workspace_id"):
            ids.add(str(meta["workspace_id"]))
    return sorted(ids)


def _require_owner(account_id: str, user_id: str) -> None:
    import auth_store

    membership = auth_store.get_membership(account_id, user_id)
    if not membership or membership["role"] != "owner":
        raise AccountLifecycleError(
            "Only the account owner can perform this action.",
            code="forbidden",
        )


def purge_operational_data(account_id: str, *, user_id: str) -> dict[str, Any]:
    """Remove businesses, runs, billing, chat, and integrations; keep account and members."""
    _require_owner(account_id, user_id)
    workspace_ids = list_chat_workspace_ids(account_id)
    chat_store.delete_workspaces(workspace_ids)

    now = _utc_now()
    with connect() as conn:
        conn.execute("DELETE FROM agent_runs WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM integration_oauth_states WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM businesses WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM account_notifications WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM billing_invoices WHERE account_id = ?", (account_id,))
        conn.execute("DELETE FROM account_chat_workspaces WHERE account_id = ?", (account_id,))
        conn.execute(
            """
            UPDATE account_subscriptions
            SET
                plan_tier = 'none',
                status = 'inactive',
                monthly_quota = 0,
                top_up_balance_runs = 0,
                plan_runs_consumed = 0,
                current_period_start = NULL,
                current_period_end = NULL,
                square_customer_id = NULL,
                square_subscription_id = NULL,
                cancel_at_period_end = 0,
                updated_at = ?
            WHERE account_id = ?
            """,
            (now, account_id),
        )
        conn.commit()

    import subscription_store

    subscription_store.ensure_row(account_id)
    support_store.delete_threads_for_account(account_id)
    return {"ok": True, "purged_workspaces": len(workspace_ids)}


def delete_account(account_id: str, *, user_id: str) -> list[str]:
    """Delete the account and users who belong only to this account."""
    _require_owner(account_id, user_id)
    workspace_ids = list_chat_workspace_ids(account_id)
    chat_store.delete_workspaces(workspace_ids)
    support_store.delete_threads_for_account(account_id)

    with connect() as conn:
        member_rows = conn.execute(
            "SELECT user_id FROM account_members WHERE account_id = ?",
            (account_id,),
        ).fetchall()
        user_ids = [row["user_id"] for row in member_rows]
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()

    deleted_users: list[str] = []
    with connect() as conn:
        for uid in user_ids:
            remaining = conn.execute(
                "SELECT 1 FROM account_members WHERE user_id = ? LIMIT 1",
                (uid,),
            ).fetchone()
            if remaining:
                continue
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
            deleted_users.append(uid)
        conn.commit()
    return deleted_users
