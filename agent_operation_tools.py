"""Agent tools: call connected integrations and databases for the active business."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import connection_store
import database_store
import integration_api_allowlist

MAX_TOOL_RESPONSE_CHARS = 48_000
MAX_HTTP_BODY_BYTES = 256_000
MAX_SQL_ROWS = 500
MAX_TOOL_ROUNDS_DEFAULT = 12

CredentialKeys = ("access_token", "api_key")


@dataclass(frozen=True)
class OperationContext:
    account_id: str
    business_id: str
    business_name: str | None = None


def integration_tools_enabled() -> bool:
    raw = (os.environ.get("AGENT_INTEGRATION_TOOLS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def max_tool_rounds() -> int:
    try:
        return max(1, min(24, int(os.environ.get("AGENT_MAX_TOOL_ROUNDS", str(MAX_TOOL_ROUNDS_DEFAULT)))))
    except ValueError:
        return MAX_TOOL_ROUNDS_DEFAULT


def build_connections_system_appendix(ctx: OperationContext) -> str:
    integrations = connection_store.list_connections(ctx.account_id, business_id=ctx.business_id)
    connected = [c for c in integrations if c.get("status") == "connected"]
    dbs = database_store.list_connections(ctx.account_id, business_id=ctx.business_id)
    lines = [
        "\n\n--- Connected operations (this business) ---",
        "You have tools to list connections and call connected third-party APIs (integration_http_request) "
        "and run SQL on connected databases (database_execute_sql).",
        "Use the provider_slug from the list below. For APIs, prefer paths from each vendor's REST docs; "
        "use absolute https URLs only when they stay under that integration's allowed API base.",
        "Confirm destructive actions with the user when reasonable; then execute when they ask.",
    ]
    if connected:
        lines.append("\nIntegrations (provider_slug · name · hint):")
        for c in connected:
            hint = c.get("credential_hint") or ""
            lines.append(f"- {c['provider_slug']} · {c['provider_name']}" + (f" · {hint}" if hint else ""))
    else:
        lines.append("\nIntegrations: none connected for this business.")
    if dbs:
        lines.append("\nDatabases (name · engine · access):")
        for db in dbs:
            lines.append(
                f"- {db['name']} · {db['engine']} · {db.get('access_mode', 'read')}"
            )
    else:
        lines.append("\nDatabases: none connected for this business.")
    return "\n".join(lines)


def gemini_function_declarations() -> list[dict[str, Any]]:
    return [
        {
            "name": "list_connected_integrations",
            "description": "List integration connections for the active business (no secrets).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "list_database_connections",
            "description": "List database connections for the active business (schema summary, no passwords).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "integration_http_request",
            "description": (
                "HTTP request to a connected integration using stored OAuth/API credentials. "
                "path_or_url: API path (e.g. /repos/owner/repo) or full https URL under the allowed base."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "provider_slug": {
                        "type": "string",
                        "description": "Integration slug from list_connected_integrations.",
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP method: GET, POST, PUT, PATCH, DELETE.",
                    },
                    "path_or_url": {
                        "type": "string",
                        "description": "Relative path or absolute https URL.",
                    },
                    "query": {
                        "type": "object",
                        "description": "Optional query string key-value pairs.",
                    },
                    "body": {
                        "type": "object",
                        "description": "Optional JSON body for POST/PUT/PATCH.",
                    },
                    "extra_headers": {
                        "type": "object",
                        "description": "Optional extra request headers (string values).",
                    },
                },
                "required": ["provider_slug", "method", "path_or_url"],
            },
        },
        {
            "name": "database_execute_sql",
            "description": (
                "Run a single SQL statement on a connected database. "
                "Respects read-only vs read_write access_mode."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "connection_name": {
                        "type": "string",
                        "description": "Database connection name from list_database_connections.",
                    },
                    "sql": {"type": "string", "description": "Single SQL statement."},
                    "parameters": {
                        "type": "array",
                        "description": "Optional bind parameters for prepared statements.",
                        "items": {},
                    },
                },
                "required": ["connection_name", "sql"],
            },
        },
    ]


def _truncate_json(value: Any) -> Any:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= MAX_TOOL_RESPONSE_CHARS:
        return value
    return {
        "truncated": True,
        "preview": text[: MAX_TOOL_RESPONSE_CHARS - 80] + "…",
        "original_chars": len(text),
    }


def _token_from_credentials(credentials: dict[str, Any]) -> str | None:
    for key in CredentialKeys:
        value = credentials.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _auth_headers(provider_slug: str, credentials: dict[str, Any]) -> dict[str, str]:
    token = _token_from_credentials(credentials)
    if not token:
        return {}
    slug = provider_slug.lower()
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "MultiWorkAgent",
    }
    if slug == "stripe":
        headers["Authorization"] = f"Bearer {token}"
    elif slug == "linear":
        headers["Authorization"] = token if token.startswith("Bearer ") else token
    elif slug == "github":
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"
    elif slug == "notion":
        headers["Authorization"] = f"Bearer {token}"
        headers["Notion-Version"] = "2022-06-28"
    elif slug == "slack":
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _execute_list_integrations(ctx: OperationContext) -> dict[str, Any]:
    rows = connection_store.list_connections(ctx.account_id, business_id=ctx.business_id)
    return {
        "integrations": [
            {
                "provider_slug": r["provider_slug"],
                "provider_name": r["provider_name"],
                "status": r["status"],
                "auth_type": r["auth_type"],
                "credential_hint": r.get("credential_hint") or "",
            }
            for r in rows
        ]
    }


def _execute_list_databases(ctx: OperationContext) -> dict[str, Any]:
    rows = database_store.list_connections(ctx.account_id, business_id=ctx.business_id)
    return {
        "databases": [
            database_store.connection_to_api(r)
            for r in rows
        ],
    }


def _execute_integration_http(ctx: OperationContext, args: dict[str, Any]) -> dict[str, Any]:
    slug = str(args.get("provider_slug") or "").strip().lower()
    method = str(args.get("method") or "GET").strip().upper()
    path_or_url = str(args.get("path_or_url") or "").strip()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
        return {"ok": False, "error": f"Unsupported method: {method}"}

    credentials = connection_store.get_connection_credentials(ctx.account_id, ctx.business_id, slug)
    if not credentials:
        return {
            "ok": False,
            "error": f"No connected credentials for provider_slug '{slug}' on this business.",
        }

    url, err = integration_api_allowlist.resolve_integration_url(
        provider_slug=slug,
        path_or_url=path_or_url,
        credentials=credentials,
    )
    if err or not url:
        return {"ok": False, "error": err or "Invalid URL."}

    query = args.get("query")
    if isinstance(query, dict) and query:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode({str(k): str(v) for k, v in query.items()})

    headers = _auth_headers(slug, credentials)
    extra = args.get("extra_headers")
    if isinstance(extra, dict):
        for key, value in extra.items():
            if isinstance(key, str) and isinstance(value, str):
                headers[key] = value

    body_bytes: bytes | None = None
    body = args.get("body")
    if body is not None and method in ("POST", "PUT", "PATCH"):
        body_bytes = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=body_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            status = int(resp.status)
            raw = resp.read(MAX_HTTP_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read(MAX_HTTP_BODY_BYTES + 1)
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"Network error: {exc.reason}"}

    truncated = len(raw) > MAX_HTTP_BODY_BYTES
    if truncated:
        raw = raw[:MAX_HTTP_BODY_BYTES]
    text = raw.decode("utf-8", errors="replace")
    parsed_body: Any = text
    try:
        parsed_body = json.loads(text) if text else None
    except json.JSONDecodeError:
        pass

    return _truncate_json(
        {
            "ok": 200 <= status < 300,
            "status": status,
            "url": url,
            "body": parsed_body,
            "truncated": truncated,
        }
    )


_WRITE_SQL = re.compile(
    r"^\s*(insert|update|delete|merge|replace|alter|drop|create|truncate|grant|revoke)\b",
    re.IGNORECASE,
)


def _sql_allowed(sql: str, access_mode: str) -> tuple[bool, str | None]:
    cleaned = sql.strip()
    if not cleaned:
        return False, "sql is empty."
    if ";" in cleaned.rstrip(";"):
        return False, "Only a single SQL statement is allowed."
    if access_mode == "read" and _WRITE_SQL.match(cleaned):
        return False, "This database connection is read-only."
    return True, None


def _execute_database_sql(ctx: OperationContext, args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("connection_name") or "").strip()
    sql = str(args.get("sql") or "").strip()
    if not name:
        return {"ok": False, "error": "connection_name is required."}

    rows = database_store.list_connections(ctx.account_id, business_id=ctx.business_id)
    match = next((r for r in rows if r["name"].lower() == name.lower()), None)
    if not match:
        return {"ok": False, "error": f"No database connection named '{name}'."}

    allowed, err = _sql_allowed(sql, str(match.get("access_mode") or "read"))
    if not allowed:
        return {"ok": False, "error": err}

    creds = database_store.get_connection_credentials(ctx.account_id, match["id"])
    if not creds:
        return {"ok": False, "error": "Could not read database credentials."}

    password = str(creds.get("password") or "")
    params = args.get("parameters")
    bind: list[Any] = list(params) if isinstance(params, list) else []

    engine = match["engine"]
    try:
        if engine == "sqlite":
            path = match["database_name"]
            conn = sqlite3.connect(path, timeout=15)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.execute(sql, bind)
                if cur.description:
                    fetched = cur.fetchmany(MAX_SQL_ROWS + 1)
                    columns = [d[0] for d in cur.description]
                    data = [dict(zip(columns, row)) for row in fetched[:MAX_SQL_ROWS]]
                    return _truncate_json(
                        {
                            "ok": True,
                            "row_count": len(data),
                            "truncated": len(fetched) > MAX_SQL_ROWS,
                            "rows": data,
                        }
                    )
                conn.commit()
                return {"ok": True, "rows_affected": cur.rowcount}
            finally:
                conn.close()

        if engine == "postgresql":
            import psycopg

            dsn = (
                f"host={match['host']} port={match['port'] or 5432} "
                f"dbname={match['database_name']} user={match['username']} password={password}"
            )
            with psycopg.connect(dsn, connect_timeout=15) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, bind)
                    if cur.description:
                        fetched = cur.fetchmany(MAX_SQL_ROWS + 1)
                        columns = [d.name for d in cur.description]
                        data = [dict(zip(columns, row)) for row in fetched[:MAX_SQL_ROWS]]
                        return _truncate_json(
                            {
                                "ok": True,
                                "row_count": len(data),
                                "truncated": len(fetched) > MAX_SQL_ROWS,
                                "rows": data,
                            }
                        )
                    conn.commit()
                    return {"ok": True, "rows_affected": cur.rowcount}

        if engine == "mysql":
            import pymysql

            conn = pymysql.connect(
                host=match["host"],
                port=match["port"] or 3306,
                user=match["username"],
                password=password,
                database=match["database_name"],
                connect_timeout=15,
                read_timeout=30,
                cursorclass=pymysql.cursors.DictCursor,
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, bind)
                    if cur.description:
                        fetched = cur.fetchmany(MAX_SQL_ROWS + 1)
                        return _truncate_json(
                            {
                                "ok": True,
                                "row_count": len(fetched[:MAX_SQL_ROWS]),
                                "truncated": len(fetched) > MAX_SQL_ROWS,
                                "rows": fetched[:MAX_SQL_ROWS],
                            }
                        )
                    conn.commit()
                    return {"ok": True, "rows_affected": cur.rowcount}
            finally:
                conn.close()

        return {"ok": False, "error": f"Unsupported engine: {engine}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def execute_tool(ctx: OperationContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "list_connected_integrations":
        return _execute_list_integrations(ctx)
    if name == "list_database_connections":
        return _execute_list_databases(ctx)
    if name == "integration_http_request":
        return _execute_integration_http(ctx, args if isinstance(args, dict) else {})
    if name == "database_execute_sql":
        return _execute_database_sql(ctx, args if isinstance(args, dict) else {})
    return {"ok": False, "error": f"Unknown tool: {name}"}
