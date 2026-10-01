"""Live global search across pages, runs, connections, businesses, and agent workspace."""

from __future__ import annotations

from typing import Any

import chat_store
import connection_store
import database_store
import run_store
from integrations_catalog import INTEGRATION_CATEGORIES

NAV_PAGES = [
    {"id": "home", "href": "/", "label": "Home"},
    {"id": "businesses", "href": "/businesses", "label": "Businesses"},
    {"id": "agent", "href": "/agent", "label": "Agent"},
    {"id": "data", "href": "/data", "label": "Data & integrations"},
    {"id": "billing", "href": "/billing", "label": "Billing & usage"},
    {"id": "settings", "href": "/settings", "label": "Settings"},
]


def _snippet(text: str, query: str, *, radius: int = 48) -> str:
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx < 0:
        return text[: radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    chunk = text[start:end].strip()
    if start > 0:
        chunk = f"…{chunk}"
    if end < len(text):
        chunk = f"{chunk}…"
    return chunk


def _add_result(
    results: list[dict[str, Any]],
    seen: set[str],
    *,
    result_id: str,
    result_type: str,
    label: str,
    meta: str,
    href: str,
    thread_id: str | None = None,
    message_id: int | None = None,
    run_id: str | None = None,
    business_id: str | None = None,
) -> None:
    if result_id in seen:
        return
    seen.add(result_id)
    row: dict[str, Any] = {
        "id": result_id,
        "type": result_type,
        "label": label,
        "meta": meta,
        "href": href,
    }
    if thread_id:
        row["thread_id"] = thread_id
    if message_id is not None:
        row["message_id"] = message_id
    if run_id:
        row["run_id"] = run_id
    if business_id:
        row["business_id"] = business_id
    results.append(row)


def _business_name(business_names: dict[str, str], business_id: str | None) -> str:
    if not business_id:
        return "All businesses"
    return business_names.get(business_id, "Business")


def _agent_href(*, business_id: str | None, thread_id: str | None) -> str:
    parts = ["/agent"]
    query: list[str] = []
    if business_id:
        query.append(f"business={business_id}")
    if query:
        parts.append("?" + "&".join(query))
    href = "".join(parts)
    return href


def _search_runs(
    results: list[dict[str, Any]],
    seen: set[str],
    *,
    account_id: str,
    query: str,
    scope_business_id: str | None,
    business_names: dict[str, str],
    limit: int,
) -> None:
    for run in run_store.search_runs(
        account_id,
        query,
        business_id=scope_business_id,
        limit=limit,
    ):
        if len(results) >= limit:
            return
        summary = run.get("summary") or "Agent run"
        label = _snippet(summary, query) if query.lower() not in summary.lower() else summary
        biz_label = _business_name(business_names, run.get("business_id"))
        status = run.get("status") or "unknown"
        meta = f"{biz_label} · Run · {status}"
        href = _agent_href(business_id=run.get("business_id"), thread_id=run.get("thread_id"))
        _add_result(
            results,
            seen,
            result_id=f"run-{run['id']}",
            result_type="agent_run",
            label=label[:120],
            meta=meta,
            href=href,
            thread_id=run.get("thread_id"),
            run_id=run["id"],
            business_id=run.get("business_id"),
        )


def _search_connections(
    results: list[dict[str, Any]],
    seen: set[str],
    *,
    account_id: str,
    query: str,
    scope_business_id: str | None,
    business_names: dict[str, str],
    limit: int,
) -> None:
    q = query.lower()
    for conn in connection_store.list_connections(account_id, business_id=scope_business_id):
        if len(results) >= limit:
            return
        haystack = " ".join(
            [
                conn.get("provider_name") or "",
                conn.get("provider_slug") or "",
                conn.get("credential_hint") or "",
                conn.get("status") or "",
            ]
        ).lower()
        if q not in haystack:
            continue
        biz_label = _business_name(business_names, conn.get("business_id"))
        _add_result(
            results,
            seen,
            result_id=f"integration-conn-{conn['id']}",
            result_type="integration_connection",
            label=conn.get("provider_name") or conn.get("provider_slug") or "Integration",
            meta=f"{biz_label} · Connected integration · {conn.get('status', '')}",
            href="/data",
            business_id=conn.get("business_id"),
        )


def _search_databases(
    results: list[dict[str, Any]],
    seen: set[str],
    *,
    account_id: str,
    query: str,
    scope_business_id: str | None,
    business_names: dict[str, str],
    limit: int,
) -> None:
    q = query.lower()
    for db in database_store.list_connections(account_id, business_id=scope_business_id):
        if len(results) >= limit:
            return
        haystack = " ".join(
            [
                db.get("name") or "",
                db.get("engine") or "",
                db.get("database_name") or "",
                db.get("connection_hint") or "",
            ]
        ).lower()
        if q not in haystack:
            continue
        biz_label = _business_name(business_names, db.get("business_id"))
        _add_result(
            results,
            seen,
            result_id=f"database-conn-{db['id']}",
            result_type="database_connection",
            label=db.get("name") or db.get("database_name") or "Database",
            meta=f"{biz_label} · Database · {db.get('engine', '')}",
            href="/data",
            business_id=db.get("business_id"),
        )


def search_workspace(
    query: str,
    workspace_ids: list[str],
    businesses: list[dict[str, Any]] | None = None,
    *,
    account_id: str | None = None,
    scope_business_id: str | None = None,
    business_names: dict[str, str] | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    names = business_names or {}
    if not names and businesses:
        names = {str(b["id"]): str(b.get("name") or "Business") for b in businesses if b.get("id")}

    for page in NAV_PAGES:
        if q in page["label"].lower():
            _add_result(
                results,
                seen,
                result_id=f"page-{page['id']}",
                result_type="page",
                label=page["label"],
                meta="Page",
                href=page["href"],
            )

    for biz in businesses or []:
        name = str(biz.get("name") or "")
        if q in name.lower():
            biz_id = str(biz.get("id") or "")
            href = f"/business/{biz_id}" if biz_id else "/businesses"
            _add_result(
                results,
                seen,
                result_id=f"business-{biz_id or name}",
                result_type="business",
                label=name,
                meta="Business",
                href=href,
                business_id=biz_id or None,
            )

    if account_id:
        run_cap = min(15, limit)
        _search_runs(
            results,
            seen,
            account_id=account_id,
            query=q,
            scope_business_id=scope_business_id,
            business_names=names,
            limit=run_cap,
        )
        _search_connections(
            results,
            seen,
            account_id=account_id,
            query=q,
            scope_business_id=scope_business_id,
            business_names=names,
            limit=limit,
        )
        _search_databases(
            results,
            seen,
            account_id=account_id,
            query=q,
            scope_business_id=scope_business_id,
            business_names=names,
            limit=limit,
        )

    for category in INTEGRATION_CATEGORIES:
        cat_label = category["label"]
        for item in category["integrations"]:
            if len(results) >= limit:
                return results[:limit]
            name = item["name"]
            slug = item["slug"]
            haystack = f"{name} {slug} {cat_label}".lower()
            if q in haystack:
                _add_result(
                    results,
                    seen,
                    result_id=f"integration-{slug}",
                    result_type="integration",
                    label=name,
                    meta=f"Catalog · {cat_label}",
                    href="/data",
                )

    for workspace_id in workspace_ids:
        for thread in chat_store.list_workspace_threads(workspace_id):
            if len(results) >= limit:
                return results[:limit]
            title = thread.get("title") or "Main chat"
            if q in title.lower():
                _add_result(
                    results,
                    seen,
                    result_id=f"thread-{workspace_id}-{thread['id']}",
                    result_type="agent_chat",
                    label=title,
                    meta="Agent chat",
                    href="/agent",
                    thread_id=thread["id"],
                )

            for msg in chat_store.list_messages(thread["id"]):
                if len(results) >= limit:
                    return results[:limit]
                content = msg.get("content") or ""
                if msg.get("role") not in ("user", "agent") or q not in content.lower():
                    continue
                msg_id = int(msg["id"])
                _add_result(
                    results,
                    seen,
                    result_id=f"msg-{thread['id']}-{msg_id}",
                    result_type="agent_message",
                    label=_snippet(content, q),
                    meta=f"{title} · Message",
                    href="/agent",
                    thread_id=thread["id"],
                    message_id=msg_id,
                )

    return results[:limit]
