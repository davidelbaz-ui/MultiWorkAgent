"""Persisted agent execution runs (chat turns and future run types)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import agent_executor
import agent_tool_trace
from agent_executor import AgentRunResult
from app_db import connect, init_app_database

SUMMARY_MAX_LEN = 120
RUNS_DAILY_LIMIT = 50
RUNS_TODAY_LIMIT = RUNS_DAILY_LIMIT  # alias
STALE_RUNNING_SECONDS = 900
_LIMIT_STATUSES = ("running", "completed", "error", "unconfigured", "timeout")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def bootstrap() -> None:
    init_app_database()


def trim_summary(text: str) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= SUMMARY_MAX_LEN:
        return clean
    return clean[: SUMMARY_MAX_LEN - 1].rstrip() + "…"


def compute_run_units(input_tokens: int, output_tokens: int, *, status: str) -> float:
    if status != "completed":
        return 0.0
    input_cap = agent_executor.run_input_cap()
    output_cap = agent_executor.run_output_cap()
    if input_cap <= 0 or output_cap <= 0:
        return 0.0
    fraction = max(input_tokens / input_cap, output_tokens / output_cap)
    return round(min(1.0, fraction), 2)


def _since_last_24h_iso() -> str:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    return since.replace(microsecond=0).isoformat()


def release_stale_running_runs(account_id: str, *, max_age_seconds: int = STALE_RUNNING_SECONDS) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat()
    now = _utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE agent_runs
            SET status = 'error',
                error_code = 'stale',
                completed_at = ?
            WHERE account_id = ?
              AND status = 'running'
              AND created_at < ?
            """,
            (now, account_id, cutoff_iso),
        )
        conn.commit()
        return int(cur.rowcount)


def count_running_runs(account_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM agent_runs
            WHERE account_id = ? AND status = 'running'
            """,
            (account_id,),
        ).fetchone()
    return int(row["c"]) if row else 0


def count_runs_last_24h(account_id: str) -> int:
    since_iso = _since_last_24h_iso()
    placeholders = ", ".join("?" for _ in _LIMIT_STATUSES)
    params: list[Any] = [account_id, since_iso, *_LIMIT_STATUSES]
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS c
            FROM agent_runs
            WHERE account_id = ?
              AND created_at >= ?
              AND status IN ({placeholders})
            """,
            params,
        ).fetchone()
    return int(row["c"]) if row else 0


def begin_chat_run(
    *,
    account_id: str,
    user_id: str | None,
    business_id: str | None,
    thread_id: str,
    summary: str,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, account_id, user_id, business_id, thread_id,
                run_type, status, error_code, summary,
                input_tokens, output_tokens, run_units, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, 'chat', 'running', NULL, ?, 0, 0, 0, ?, NULL)
            """,
            (
                run_id,
                account_id,
                user_id,
                business_id,
                thread_id,
                trim_summary(summary),
                now,
            ),
        )
        conn.commit()
    row = get_run(account_id, run_id)
    if not row:
        raise RuntimeError("failed to begin run")
    return row


def finish_chat_run(
    account_id: str,
    run_id: str,
    result: AgentRunResult,
) -> dict[str, Any] | None:
    now = _utc_now()
    run_units = compute_run_units(
        result.input_tokens,
        result.output_tokens,
        status=result.status,
    )
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE agent_runs
            SET status = ?,
                error_code = ?,
                input_tokens = ?,
                output_tokens = ?,
                run_units = ?,
                completed_at = ?
            WHERE account_id = ? AND id = ? AND status = 'running'
            """,
            (
                result.status,
                result.error_code,
                result.input_tokens,
                result.output_tokens,
                run_units,
                now,
                account_id,
                run_id,
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            return get_run(account_id, run_id)

    import usage_metering

    usage_metering.meter_completed_run(account_id, run_id)
    finished = get_run(account_id, run_id)
    if finished:
        import notification_events

        notification_events.notify_run_finished(account_id, finished)
        notification_events.notify_after_usage_metered(account_id)
        try:
            import account_activity_store

            account_activity_store.record(
                account_id,
                category="agent",
                action="run_completed",
                summary=f"Agent run {finished.get('status')}: {finished.get('summary') or run_id}",
                user_id=finished.get("user_id"),
                detail={
                    "run_id": run_id,
                    "status": finished.get("status"),
                    "run_units": finished.get("run_units"),
                },
            )
        except Exception:
            pass
    return finished


def record_blocked_run(
    *,
    account_id: str,
    user_id: str | None,
    business_id: str | None,
    thread_id: str,
    summary: str,
    error_code: str,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, account_id, user_id, business_id, thread_id,
                run_type, status, error_code, summary,
                input_tokens, output_tokens, run_units, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, 'chat', 'blocked', ?, ?, 0, 0, 0, ?, ?)
            """,
            (
                run_id,
                account_id,
                user_id,
                business_id,
                thread_id,
                error_code,
                trim_summary(summary),
                now,
                now,
            ),
        )
        conn.commit()
    row = get_run(account_id, run_id)
    if not row:
        raise RuntimeError("failed to record blocked run")
    return row


def record_chat_run(
    *,
    account_id: str,
    user_id: str | None,
    business_id: str | None,
    thread_id: str,
    result: AgentRunResult,
    summary: str,
) -> dict[str, Any]:
    """Synchronous helper: begin and finish in one step (tests and legacy callers)."""
    run = begin_chat_run(
        account_id=account_id,
        user_id=user_id,
        business_id=business_id,
        thread_id=thread_id,
        summary=summary,
    )
    finished = finish_chat_run(account_id, run["id"], result)
    return finished or run


def list_runs_for_account(account_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 300))
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id, account_id, user_id, business_id, thread_id,
                run_type, status, error_code, summary,
                input_tokens, output_tokens, run_units, created_at, completed_at
            FROM agent_runs
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def get_run(account_id: str, run_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                id, account_id, user_id, business_id, thread_id,
                run_type, status, error_code, summary,
                input_tokens, output_tokens, run_units, created_at, completed_at
            FROM agent_runs
            WHERE account_id = ? AND id = ?
            """,
            (account_id, run_id),
        ).fetchone()
    return _row_to_run(row) if row else None


def get_latest_for_thread(account_id: str, thread_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                id, account_id, user_id, business_id, thread_id,
                run_type, status, error_code, summary,
                input_tokens, output_tokens, run_units, created_at, completed_at
            FROM agent_runs
            WHERE account_id = ? AND thread_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (account_id, thread_id),
        ).fetchone()
    return _row_to_run(row) if row else None


def count_runs_today(account_id: str) -> int:
    """Runs in the rolling 24-hour window (daily breaker)."""
    return count_runs_last_24h(account_id)


def search_runs(
    account_id: str,
    query: str,
    *,
    business_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    limit = max(1, min(limit, 30))
    pattern = f"%{q}%"
    where = "r.account_id = ?"
    params: list[Any] = [account_id]
    if business_id:
        where += " AND r.business_id = ?"
        params.append(business_id)
    params.extend([pattern, pattern, pattern, pattern, limit])
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT DISTINCT
                r.id, r.account_id, r.user_id, r.business_id, r.thread_id,
                r.run_type, r.status, r.error_code, r.summary,
                r.input_tokens, r.output_tokens, r.run_units, r.created_at, r.completed_at
            FROM agent_runs r
            LEFT JOIN agent_run_tool_calls t
                ON t.run_id = r.id AND t.account_id = r.account_id
            WHERE {where}
              AND (
                LOWER(r.summary) LIKE ?
                OR LOWER(COALESCE(r.error_code, '')) LIKE ?
                OR LOWER(r.id) LIKE ?
                OR LOWER(t.tool_name) LIKE ?
              )
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def list_recent_runs(
    account_id: str,
    *,
    business_id: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 50))
    where = "account_id = ?"
    params: list[Any] = [account_id]
    if business_id:
        where += " AND business_id = ?"
        params.append(business_id)
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                id, account_id, user_id, business_id, thread_id,
                run_type, status, error_code, summary,
                input_tokens, output_tokens, run_units, created_at, completed_at
            FROM agent_runs
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def list_recent_for_display(
    account_id: str,
    *,
    business_id: str | None = None,
    business_names: dict[str, str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    runs = list_recent_runs(account_id, business_id=business_id, limit=limit)
    names = business_names or {}
    display: list[dict[str, Any]] = []
    for run in runs:
        display.append(_run_to_display_row(run, names))
    return display


def _parse_json_field(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def replace_tool_calls(
    account_id: str,
    run_id: str,
    calls: list[dict[str, Any]],
) -> None:
    now = _utc_now()
    with connect() as conn:
        conn.execute(
            "DELETE FROM agent_run_tool_calls WHERE account_id = ? AND run_id = ?",
            (account_id, run_id),
        )
        for seq, call in enumerate(calls):
            conn.execute(
                """
                INSERT INTO agent_run_tool_calls (
                    run_id, account_id, seq, tool_name, input_json, output_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    account_id,
                    seq,
                    str(call.get("tool_name") or call.get("name") or "tool"),
                    json.dumps(call.get("input") or {}, ensure_ascii=False, default=str),
                    json.dumps(call.get("output"), ensure_ascii=False, default=str)
                    if call.get("output") is not None
                    else None,
                    str(call.get("status") or "ok"),
                    now,
                ),
            )
        conn.commit()


def list_tool_calls(account_id: str, run_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, tool_name, input_json, output_json, status, seq, created_at
            FROM agent_run_tool_calls
            WHERE account_id = ? AND run_id = ?
            ORDER BY seq ASC
            """,
            (account_id, run_id),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = {
            "id": int(row["id"]),
            "tool_name": row["tool_name"],
            "input": _parse_json_field(row["input_json"]),
            "output": _parse_json_field(row["output_json"]),
            "status": row["status"],
            "seq": int(row["seq"]),
            "created_at": row["created_at"],
        }
        item["label"] = agent_tool_trace.tool_call_display_label(item)
        items.append(item)
    return items


def run_to_api_payload(run: dict[str, Any]) -> dict[str, Any]:
    tool_calls = list_tool_calls(run["account_id"], run["id"])
    return {
        "id": run["id"],
        "status": run["status"],
        "error_code": run.get("error_code"),
        "summary": run.get("summary") or "",
        "input_tokens": run["input_tokens"],
        "output_tokens": run["output_tokens"],
        "run_units": run["run_units"],
        "run_input_cap": agent_executor.run_input_cap(),
        "run_output_cap": agent_executor.run_output_cap(),
        "thread_id": run["thread_id"],
        "business_id": run.get("business_id"),
        "created_at": run["created_at"],
        "tool_calls": tool_calls,
    }


def _run_to_display_row(run: dict[str, Any], business_names: dict[str, str]) -> dict[str, Any]:
    bid = run.get("business_id")
    if bid and bid in business_names:
        business_label = business_names[bid]
    elif bid:
        business_label = "Business"
    else:
        business_label = "All businesses"

    status = run["status"]
    ui_status = "completed" if status == "completed" else "failed"
    if status == "running":
        ui_status = "completed"

    units = run["run_units"]
    if units == 0:
        units_label = "0"
    elif units >= 1:
        units_label = "1 run"
    else:
        units_label = f"{units:g} run"

    return {
        "id": run["id"],
        "time": _format_run_time(run["created_at"]),
        "business": business_label,
        "summary": run.get("summary") or "—",
        "units": units_label,
        "status": ui_status,
        "raw_status": status,
    }


def _format_run_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt.astimezone(timezone.utc)
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{seconds // 60} min ago"
        if seconds < 86400:
            return f"{seconds // 3600} hr ago"
        return dt.astimezone(timezone.utc).strftime("%b %d, %H:%M UTC")
    except ValueError:
        return iso


def _row_to_run(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "account_id": row["account_id"],
        "user_id": row["user_id"],
        "business_id": row["business_id"],
        "thread_id": row["thread_id"],
        "run_type": row["run_type"],
        "status": row["status"],
        "error_code": row["error_code"],
        "summary": row["summary"],
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "run_units": float(row["run_units"] or 0),
        "created_at": row["created_at"],
        "completed_at": row["completed_at"] if "completed_at" in row.keys() else None,
    }
