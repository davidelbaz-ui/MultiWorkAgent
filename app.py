"""MultiWorkAgent — Flask application."""

from __future__ import annotations

import os
import uuid

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

from flask import (
    Flask,
    Response,
    abort,
    g,
    jsonify,
    redirect,
    request,
    render_template,
    session,
    stream_with_context,
    url_for,
)

import app_logging
import app_state
import http_rate_limit
from app_config import load_app_config, apply_flask_config, validate_production_secrets
from pg_storage import should_trust_session_membership

import account_lifecycle
import agent_executor
import auth_store
import business_store
import chat_store
import connection_store
import database_introspect
import database_store
import integration_oauth
import knowledge_store
import login_oauth
import login_oauth_state_store
from app_urls import (
    billing_checkout_return_url,
    integration_oauth_callback_url,
    login_oauth_callback_url,
    square_webhook_notification_url,
)
import invoice_store
import notification_store
import settings_store
import site_settings_store
import support_store
import square_billing
import subscription_plans
import subscription_store
import team_invite_store
import user_notification_store
import oauth_state_store
import run_limits
import run_store
from run_limits import RunLimitError
import global_search
from integrations_catalog import INTEGRATION_CATEGORIES, catalog_for_api, integration_count

APP_CONFIG = load_app_config()
app = Flask(__name__)
apply_flask_config(app, APP_CONFIG)
app.secret_key = APP_CONFIG.secret_key
LOGGER = app_logging.configure_logging(APP_CONFIG)
for _warning in validate_production_secrets(APP_CONFIG):
    LOGGER.warning(_warning)

if APP_CONFIG.trust_proxy:
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

NAV = [
    {"id": "home", "href": "/", "label": "Home", "icon": "home"},
    {"id": "businesses", "href": "/businesses", "label": "Businesses", "icon": "businesses"},
    {"id": "agent", "href": "/agent", "label": "Agent", "icon": "agent"},
    {"id": "data", "href": "/data", "label": "Data & integrations", "icon": "data"},
    {"id": "billing", "href": "/billing", "label": "Billing & usage", "icon": "billing"},
    {"id": "settings", "href": "/settings", "label": "Settings", "icon": "settings"},
]

CHAT_SCOPE_ALL = "__all__"
AUTH_PUBLIC_ENDPOINTS = frozenset(
    {
        "login",
        "signup",
        "static",
        "health",
        "integrations_oauth_callback",
        "square_webhook",
        "index",
        "favicon",
        "login_oauth_start",
        "login_oauth_callback",
        "privacy_policy",
        "terms_and_conditions",
        "licence_agreement",
    }
)

RATE_LIMITED_AUTH_ENDPOINTS = frozenset({"login", "signup"})

DB_PUBLIC_ENDPOINTS = frozenset(
    {
        "health",
        "static",
        "favicon",
        "index",
        "privacy_policy",
        "terms_and_conditions",
        "licence_agreement",
    }
)

DB_READY = False
DB_INIT_ERROR: str | None = None


def _publish_db_status() -> None:
    global DB_READY, DB_INIT_ERROR
    app_state.set_database_status(ready=DB_READY, error=DB_INIT_ERROR)
    app.config["DB_READY"] = DB_READY
    app.config["DB_INIT_ERROR"] = DB_INIT_ERROR


def bootstrap_application_stores() -> None:
    global DB_READY, DB_INIT_ERROR
    from db_connection import database_url, deployment_database_error

    misconfig = deployment_database_error()
    if misconfig:
        DB_INIT_ERROR = misconfig
        DB_READY = False
        LOGGER.error("database_misconfigured %s", DB_INIT_ERROR)
        _publish_db_status()
        return
    if not database_url():
        DB_INIT_ERROR = (
            "DATABASE_URL is not set. Connect Vercel Postgres (POSTGRES_URL) or set DATABASE_URL "
            "under Project Settings / Environment Variables, then redeploy."
        )
        DB_READY = False
        LOGGER.error("database_unconfigured %s", DB_INIT_ERROR)
        _publish_db_status()
        return
    try:
        account_lifecycle.bootstrap()
        auth_store.bootstrap()
        business_store.bootstrap()
        run_store.bootstrap()
        connection_store.bootstrap()
        oauth_state_store.bootstrap()
        login_oauth_state_store.bootstrap()
        database_store.bootstrap()
        knowledge_store.bootstrap()
        subscription_store.bootstrap()
        invoice_store.bootstrap()
        notification_store.bootstrap()
        settings_store.bootstrap()
        support_store.bootstrap()
        site_settings_store.bootstrap()
        chat_store.bootstrap()
        user_notification_store.bootstrap()
        team_invite_store.bootstrap()
        DB_READY = True
        DB_INIT_ERROR = None
        LOGGER.info("database_bootstrap_ok")
    except Exception as exc:
        err_text = str(exc).strip() or repr(exc)
        if "ConnectionTimeout" in type(exc).__name__ or "timeout" in err_text.lower():
            DB_INIT_ERROR = (
                "Could not reach PostgreSQL (connection timed out). "
                "For local dev: run `docker compose up -d` and set DATABASE_URL to "
                "postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent in .env. "
                "If .env has a remote Vercel/Neon URL, use that only when the network can reach it."
            )
        else:
            DB_INIT_ERROR = f"Database setup failed: {exc}"
        DB_READY = False
        LOGGER.exception("database_bootstrap_failed")
    _publish_db_status()


bootstrap_application_stores()

from admin_routes import admin_bp

app.register_blueprint(admin_bp)


def _safe_next_url(raw: str | None) -> str:
    if not raw or not raw.startswith("/") or raw.startswith("//"):
        return url_for("index")
    return raw


def _auth_template_context() -> dict:
    return {"oauth_providers": login_oauth.configured_login_providers()}


def _site_copy(keys: list[str]) -> dict[str, str]:
    if not DB_READY:
        return {}
    try:
        return site_settings_store.get_many(keys)
    except Exception:
        LOGGER.exception("site_settings_read_failed")
        return {}


def _legal_template_context() -> dict:
    if session.get("user_id") and session.get("account_id"):
        back_href = url_for("settings")
        back_label = "Back to settings"
    elif session.get("user_id"):
        back_href = url_for("index")
        back_label = "Back to home"
    else:
        back_href = url_for("index")
        back_label = "Back to home"
    return {
        "legal_back_href": back_href,
        "legal_back_label": back_label,
        "legal_last_updated": "October 5, 2026",
        "legal_year": 2026,
    }


@app.context_processor
def _inject_auth_oauth_context() -> dict:
    if request.path.startswith("/admin"):
        return {}
    from pg_storage import storage_banner_for_ui

    return {
        **_auth_template_context(),
        "storage_warning": storage_banner_for_ui(),
    }


def _login_session(user: dict, membership: dict) -> None:
    auth_store.touch_last_login(user["id"])
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["account_id"] = membership["account_id"]
    session["role"] = membership["role"]
    session["user_email"] = user.get("email") or ""
    session["user_display_name"] = user.get("display_name") or user.get("name") or ""
    try:
        team_invite_store.sync_invites_for_user(user["id"], user.get("email") or "")
    except Exception:
        LOGGER.exception("team_invite_sync_failed user_id=%s", user.get("id"))


def _apply_invite_session(membership: dict) -> None:
    session["account_id"] = membership["account_id"]
    session["role"] = membership["role"]


def _notifications_feed(account_id: str, user_id: str) -> tuple[list[dict], int]:
    account_rows = notification_store.list_notifications(account_id)
    for row in account_rows:
        row["scope"] = "account"
    user_rows = user_notification_store.list_for_user(user_id)
    merged = account_rows + user_rows
    merged.sort(key=lambda row: row.get("created_at") or "", reverse=True)
    merged = merged[:50]
    api_rows = []
    for row in merged:
        if row.get("scope") == "user":
            api_rows.append(user_notification_store.notification_to_api(row))
        else:
            api_rows.append(notification_store.notification_to_api(row))
    unread = notification_store.unread_count(account_id) + user_notification_store.unread_count(
        user_id
    )
    return api_rows, unread


def _membership_from_session(user_id: str, account_id: str) -> dict | None:
    role = session.get("role")
    if role not in auth_store.ROLES:
        return None
    return {
        "account_id": account_id,
        "user_id": user_id,
        "role": role,
        "role_label": auth_store.ROLE_LABELS.get(role, role),
    }


def _resolve_membership(user_id: str, account_id: str) -> dict | None:
    membership = auth_store.get_membership(account_id, user_id)
    if membership:
        return membership
    if should_trust_session_membership():
        return _membership_from_session(user_id, account_id)
    return None


def _session_user_profile(user_id: str) -> dict | None:
    user = auth_store.get_user(user_id)
    if user:
        return user
    email = (session.get("user_email") or "").strip()
    if not email:
        return None
    name = (session.get("user_display_name") or "").strip()
    return {
        "id": user_id,
        "email": email,
        "display_name": name,
        "name": name or email,
        "created_at": "",
    }


def _auth_context() -> dict:
    user_id = session.get("user_id")
    account_id = session.get("account_id")
    if not user_id or not account_id:
        return {
            "current_user": None,
            "account_role": None,
            "account_role_label": None,
            "team_members": [],
        }
    user = _session_user_profile(user_id)
    membership = _resolve_membership(user_id, account_id)
    team = auth_store.list_account_members(account_id) if account_id else []
    return {
        "current_user": user,
        "account_role": membership["role"] if membership else None,
        "account_role_label": membership["role_label"] if membership else None,
        "team_members": team,
    }


def _ensure_account_id() -> str:
    account_id = session.get("account_id")
    if not account_id:
        abort(401)
    return account_id


@app.before_request
def require_database_ready():
    if DB_READY:
        return None
    if request.path.startswith("/admin"):
        return None
    from db_connection import database_env_diagnostics

    endpoint = request.endpoint or ""
    base = endpoint.split(".")[0]
    if base in DB_PUBLIC_ENDPOINTS:
        return None
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": DB_INIT_ERROR or "database not configured",
                    "code": "database_unconfigured",
                }
            ),
            503,
        )
    return (
        render_template(
            "db_unconfigured.html",
            db_error=DB_INIT_ERROR,
            db_env=database_env_diagnostics(),
            **_legal_template_context(),
        ),
        503,
    )


@app.before_request
def enforce_maintenance_mode():
    if not DB_READY:
        return None
    if request.path.startswith("/admin"):
        return None
    try:
        enabled, message = site_settings_store.maintenance_mode()
    except Exception:
        return None
    if not enabled:
        return None
    endpoint = (request.endpoint or "").split(".")[0]
    if endpoint in {"health", "static", "favicon"}:
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "maintenance", "message": message}), 503
    return render_template("maintenance.html", message=message), 503


@app.before_request
def assign_request_id():
    g.request_id = uuid.uuid4().hex[:12]


@app.before_request
def enforce_http_rate_limits():
    if not APP_CONFIG.rate_limit_enabled:
        return None
    endpoint = request.endpoint or ""
    base = endpoint.split(".")[0]
    remote = request.headers.get("X-Forwarded-For", request.remote_addr)
    if remote and "," in remote:
        remote = remote.split(",", 1)[0].strip()

    if base in RATE_LIMITED_AUTH_ENDPOINTS and request.method == "POST":
        cap = (
            APP_CONFIG.rate_limit_login_per_minute
            if base == "login"
            else APP_CONFIG.rate_limit_signup_per_minute
        )
        if not http_rate_limit.allow(f"auth:{base}", remote, max_events=cap):
            app_logging.log_event(
                LOGGER,
                "rate_limit_exceeded",
                kind="auth",
                endpoint=base,
                remote_addr=remote,
                request_id=getattr(g, "request_id", None),
            )
            if request.path.startswith("/api/"):
                return jsonify({"error": "too many requests; try again shortly"}), 429
            if base == "login":
                return render_template(
                    "login.html",
                    error="Too many attempts. Please wait a minute and try again.",
                    next_url=request.args.get("next", ""),
                ), 429
            return render_template(
                "signup.html",
                error="Too many attempts. Please wait a minute and try again.",
            ), 429

    if request.path.startswith("/api/") and base not in AUTH_PUBLIC_ENDPOINTS:
        if not http_rate_limit.allow(
            "api",
            remote,
            max_events=APP_CONFIG.rate_limit_api_per_minute,
        ):
            return jsonify({"error": "too many requests; try again shortly"}), 429
    return None


@app.before_request
def enforce_auth_and_roles():
    if request.path.startswith("/admin"):
        return None
    endpoint = request.endpoint or ""
    if endpoint.split(".")[0] in AUTH_PUBLIC_ENDPOINTS or endpoint == "static":
        return None

    user_id = session.get("user_id")
    account_id = session.get("account_id")
    if not user_id or not account_id:
        if request.path.startswith("/api/"):
            return jsonify({"error": "authentication required"}), 401
        next_url = request.full_path if request.query_string else request.path
        if next_url.endswith("?") and not request.query_string:
            next_url = request.path
        return redirect(url_for("login", next=next_url))

    membership = _resolve_membership(user_id, account_id)
    if not membership:
        session.clear()
        if request.path.startswith("/api/"):
            return jsonify({"error": "authentication required"}), 401
        return redirect(url_for("login"))

    session["role"] = membership["role"]

    if (
        membership["role"] == "viewer"
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and endpoint != "logout"
    ):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Viewers cannot modify workspace data"}), 403
        abort(403)

    return None


@app.after_request
def apply_security_headers(response):
    if request.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    if APP_CONFIG.session_cookie_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    if request.path.startswith("/admin"):
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    return response


@app.after_request
def log_http_request(response):
    if request.endpoint == "static":
        return response
    app_logging.log_event(
        LOGGER,
        "http_request",
        request_id=getattr(g, "request_id", None),
        method=request.method,
        path=request.path,
        status=response.status_code,
        remote_addr=request.remote_addr,
        account_id=session.get("account_id"),
    )
    return response


@app.errorhandler(500)
def handle_internal_error(_exc):
    LOGGER.exception("unhandled_error request_id=%s", getattr(g, "request_id", None))
    if request.path.startswith("/api/"):
        return jsonify({"error": "internal server error"}), 500
    return render_template("error.html", code=500, message="Something went wrong."), 500


@app.get("/health")
def health():
    from db_connection import database_env_diagnostics

    payload = {
        "ok": DB_READY,
        "env": APP_CONFIG.app_env,
        "database": "ready" if DB_READY else "unconfigured",
        "database_env": database_env_diagnostics(),
    }
    if DB_INIT_ERROR:
        payload["database_error"] = DB_INIT_ERROR
    import admin_auth

    payload["admin_configured"] = admin_auth.admin_configured()
    status = 200 if DB_READY else 503
    return jsonify(payload), status


@app.get("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="logo.svg"))


def _account_businesses() -> list[dict]:
    return business_store.list_businesses(_ensure_account_id())


def _chat_scope_key() -> str:
    business_id = session.get("selected_business_id")
    return business_id if business_id else CHAT_SCOPE_ALL


def _get_selected_business_id() -> str | None:
    business_id = session.get("selected_business_id")
    if not business_id:
        return None
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        session.pop("selected_business_id", None)
        return None
    return business_id


def _set_selected_business_id(business_id: str | None) -> None:
    if business_id:
        session["selected_business_id"] = business_id
    else:
        session.pop("selected_business_id", None)


def _business_switcher_label() -> str:
    business_id = _get_selected_business_id()
    if not business_id:
        return "All businesses"
    business = business_store.get_business(_ensure_account_id(), business_id)
    return business["name"] if business else "All businesses"


def _businesses_for_search() -> list[dict]:
    businesses = _account_businesses()
    business_id = _get_selected_business_id()
    if not business_id:
        return businesses
    match = next((b for b in businesses if b["id"] == business_id), None)
    return [match] if match else []


def _chat_workspaces_map() -> dict[str, str]:
    raw = session.get("chat_workspaces")
    workspaces: dict[str, str] = dict(raw) if isinstance(raw, dict) else {}

    legacy_workspace = session.get("chat_workspace_id")
    if legacy_workspace and CHAT_SCOPE_ALL not in workspaces:
        workspaces[CHAT_SCOPE_ALL] = legacy_workspace
        session.pop("chat_workspace_id", None)

    session["chat_workspaces"] = workspaces
    return workspaces


def _active_threads_map() -> dict[str, str]:
    raw = session.get("active_thread_by_scope")
    mapping: dict[str, str] = dict(raw) if isinstance(raw, dict) else {}

    legacy_active = session.get("active_thread_id")
    if legacy_active and CHAT_SCOPE_ALL not in mapping:
        mapping[CHAT_SCOPE_ALL] = legacy_active

    session["active_thread_by_scope"] = mapping
    return mapping


def _ensure_chat_session() -> tuple[str, str]:
    scope = _chat_scope_key()
    workspaces = _chat_workspaces_map()
    active_map = _active_threads_map()
    legacy_thread = session.get("agent_thread_id")

    workspace_id = workspaces.get(scope)
    if not workspace_id:
        workspace_id = str(uuid.uuid4())
        workspaces[scope] = workspace_id
        session["chat_workspaces"] = workspaces

    threads = chat_store.list_workspace_threads(workspace_id)
    if legacy_thread:
        chat_store.adopt_legacy_thread(legacy_thread, workspace_id)
        active_map[scope] = legacy_thread
        session.pop("agent_thread_id", None)
    elif not threads:
        active_map[scope] = chat_store.create_workspace_with_main(workspace_id)
    else:
        active = active_map.get(scope)
        if not active or not any(t["id"] == active for t in threads):
            main = next((t for t in threads if t.get("kind") == "main"), threads[0])
            active_map[scope] = main["id"]

    session["active_thread_by_scope"] = active_map
    active_thread_id = active_map[scope]
    session["active_thread_id"] = active_thread_id
    account_lifecycle.remember_chat_workspace(
        _ensure_account_id(),
        scope_key=scope,
        workspace_id=workspace_id,
    )
    return workspace_id, active_thread_id


def _chat_workspace_ids_for_search() -> list[str]:
    business_id = _get_selected_business_id()
    workspaces = _chat_workspaces_map()
    if business_id:
        workspace_id = workspaces.get(business_id)
        if not workspace_id:
            workspace_id, _ = _ensure_chat_session()
        return [workspace_id]

    ids: list[str] = []
    for key in (CHAT_SCOPE_ALL, *sorted(workspaces.keys())):
        if key in workspaces and workspaces[key] not in ids:
            ids.append(workspaces[key])
    if not ids:
        workspace_id, _ = _ensure_chat_session()
        ids.append(workspace_id)
    return ids


def _selection_context() -> dict:
    account_id = _ensure_account_id()
    selected_id = _get_selected_business_id()
    selected = (
        business_store.get_business(account_id, selected_id) if selected_id else None
    )
    return {
        "selected_business_id": selected_id,
        "selected_business": selected,
        "business_switcher_label": _business_switcher_label(),
        "businesses": _account_businesses(),
    }


def _persist_active_thread(thread_id: str) -> None:
    scope = _chat_scope_key()
    active_map = _active_threads_map()
    active_map[scope] = thread_id
    session["active_thread_by_scope"] = active_map
    session["active_thread_id"] = thread_id


def _active_thread_id() -> str:
    _, thread_id = _ensure_chat_session()
    return thread_id


def _business_names_by_id() -> dict[str, str]:
    return {b["id"]: b["name"] for b in _account_businesses()}


def _integration_connections_for_display(
    *,
    business_id: str | None = None,
) -> list[dict]:
    account_id = _ensure_account_id()
    scope_id = business_id if business_id is not None else _get_selected_business_id()
    connections = connection_store.list_connections(account_id, business_id=scope_id)
    names = _business_names_by_id()
    for row in connections:
        row["business_name"] = names.get(row["business_id"], "Business")
    return connections


def _oauth_redirect_uri() -> str:
    return integration_oauth_callback_url()


def _database_connections_for_display(
    *,
    business_id: str | None = None,
) -> list[dict]:
    account_id = _ensure_account_id()
    scope_id = business_id if business_id is not None else _get_selected_business_id()
    rows = database_store.list_connections(account_id, business_id=scope_id)
    names = _business_names_by_id()
    display: list[dict] = []
    for row in rows:
        access = "read-only" if row["access_mode"] == "read" else "read/write"
        synced = row.get("schema_synced_at") or "—"
        display.append(
            {
                "id": row["id"],
                "business_id": row["business_id"],
                "business_name": names.get(row["business_id"], "Business"),
                "name": row["name"],
                "engine": row["engine"],
                "access": access,
                "last_query": database_store.connection_to_api(row)["schema_summary"],
                "connection_hint": row["connection_hint"],
                "schema_synced_at": synced,
                "table_count": (row.get("schema") or {}).get("table_count"),
            }
        )
    return display


def _connection_public(row: dict) -> dict:
    return {
        "id": row["id"],
        "business_id": row["business_id"],
        "business_name": row.get("business_name"),
        "provider_slug": row["provider_slug"],
        "provider_name": row["provider_name"],
        "auth_type": row["auth_type"],
        "status": row["status"],
        "credential_hint": row.get("credential_hint") or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _billing_fields() -> dict:
    account_id = _ensure_account_id()
    subscription_store.ensure_row(account_id)
    summary = subscription_store.billing_summary(account_id)
    return {
        "plan": summary["plan"],
        "plan_tier": summary["plan_tier"],
        "billing_interval": summary.get("billing_interval") or "monthly",
        "usage_used": summary.get("usage_used", 0),
        "usage_quota": summary["usage_quota"],
        "top_up_balance": summary["top_up_balance"],
        "billing_period_end": summary["billing_period_end"],
        "subscription_status": summary["status"],
        "cancel_at_period_end": summary["cancel_at_period_end"],
        "billing_mode": square_billing.billing_mode(),
        "invoices": invoice_store.list_for_display(account_id),
    }


def _assert_billing_owner() -> None:
    if session.get("role") != "owner":
        raise PermissionError("only account owners can manage billing")


def _runs_dashboard_fields() -> dict:
    account_id = _ensure_account_id()
    business_id = _get_selected_business_id()
    limits = run_limits.limits_snapshot(account_id)
    usage = limits.get("usage") or {}
    free_tier = bool(usage.get("free_tier"))
    return {
        "recent_runs": run_store.list_recent_for_display(
            account_id,
            business_id=business_id,
            business_names=_business_names_by_id(),
            limit=10,
        ),
        "runs_today": limits["runs_display_used"],
        "runs_daily_max": limits["runs_display_max"],
        "runs_limit_free_tier": free_tier,
        "concurrent": limits["concurrent"],
        "concurrent_max": limits["concurrent_max"],
        "run_limits": limits,
    }


def _agent_run_payload(thread_id: str | None = None, extra: dict | None = None) -> dict:
    account_id = _ensure_account_id()
    record = None
    if thread_id:
        record = run_store.get_latest_for_thread(account_id, thread_id)
    if not record:
        run_id = session.get("last_agent_run_id")
        if run_id:
            record = run_store.get_run(account_id, run_id)
    if record:
        payload = run_store.run_to_api_payload(record)
    else:
        payload = {
            "id": None,
            "status": "idle",
            "summary": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "run_units": 0,
            "run_input_cap": agent_executor.run_input_cap(),
            "run_output_cap": agent_executor.run_output_cap(),
            "error_code": None,
            "thread_id": thread_id,
            "business_id": _get_selected_business_id(),
            "created_at": None,
            "tool_calls": [],
        }
    limits = run_limits.limits_snapshot(account_id)
    payload["runs_today"] = limits["runs_display_used"]
    payload["runs_daily_max"] = limits["runs_display_max"]
    payload["limits"] = limits
    if extra:
        payload.update(extra)
    return payload


def _agent_page_inspector(thread_id: str) -> dict:
    run = _agent_run_payload(thread_id=thread_id)
    return {
        "run_input_tokens": run["input_tokens"],
        "run_output_tokens": run["output_tokens"],
        "run_input_cap": run["run_input_cap"],
        "run_output_cap": run["run_output_cap"],
        "runs_today": run["runs_today"],
        "runs_daily_max": run["runs_daily_max"],
        "run_tool_calls": [tc.get("label") or tc.get("tool_name") for tc in run.get("tool_calls") or []],
    }


def _enrich_agent_state(state: dict) -> dict:
    state["scope_label"] = _business_switcher_label()
    state["selected_business_id"] = _get_selected_business_id()
    thread_id = state.get("active_thread_id") or state.get("thread_id")
    state["run"] = _agent_run_payload(thread_id=thread_id)
    limits = state["run"].get("limits") or run_limits.limits_snapshot(_ensure_account_id())
    state["limits"] = limits
    state["concurrent"] = limits["concurrent"]
    state["concurrent_max"] = limits["concurrent_max"]
    state["runs_today"] = limits.get("runs_display_used", limits["runs_24h"])
    state["runs_daily_max"] = limits.get("runs_display_max", limits["runs_daily_max"])
    state["runs_limit_free_tier"] = bool((limits.get("usage") or {}).get("free_tier"))
    usage = limits.get("usage") or {}
    summary = subscription_store.billing_summary(_ensure_account_id())
    state["usage_used"] = usage.get("usage_used", summary.get("usage_used"))
    state["usage_quota"] = usage.get("usage_quota", summary.get("usage_quota"))
    state["plan"] = summary.get("plan")
    run = state.get("run") or {}
    state["run_tool_calls"] = [
        tc.get("label") or tc.get("tool_name") for tc in run.get("tool_calls") or []
    ]
    return state


def _business_name_for_agent() -> str | None:
    business_id = _get_selected_business_id()
    if not business_id:
        return None
    business = business_store.get_business(_ensure_account_id(), business_id)
    return business["name"] if business else None


def _persist_agent_run_result(
    thread_id: str,
    account_id: str,
    run_id: str,
    result: agent_executor.AgentRunResult,
) -> tuple[dict | None, dict]:
    agent_message = None
    if result.content:
        if result.status == "completed" or (
            result.error_code == "cancelled" and result.content.strip()
        ):
            agent_message = chat_store.create_agent_message(thread_id, result.content)
        else:
            agent_message = chat_store.create_system_message(thread_id, result.content)

    record = run_store.finish_chat_run(account_id, run_id, result) or run_store.get_run(
        account_id, run_id
    )
    if record and result.tool_calls:
        run_store.replace_tool_calls(account_id, record["id"], result.tool_calls)
    return agent_message, record or {}


def _agent_sse(payload: dict) -> str:
    import json

    # Pad frames so proxies (e.g. Vercel) flush incremental chunks instead of buffering the whole stream.
    data = f"data: {json.dumps(payload, default=str)}\n\n"
    min_frame = 2048
    if len(data) < min_frame:
        data += ":" + (" " * (min_frame - len(data) - 1)) + "\n"
    return data + "\n"


def _execute_agent_turn(thread_id: str, *, trigger_summary: str) -> dict:
    account_id = _ensure_account_id()
    run = run_store.begin_chat_run(
        account_id=account_id,
        user_id=session.get("user_id"),
        business_id=_get_selected_business_id(),
        thread_id=thread_id,
        summary=trigger_summary,
    )
    session["last_agent_run_id"] = run["id"]

    result = agent_executor.generate_reply(
        thread_id,
        scope_label=_business_switcher_label(),
        business_name=_business_name_for_agent(),
        account_id=account_id,
        business_id=_get_selected_business_id(),
    )

    agent_message, record = _persist_agent_run_result(thread_id, account_id, run["id"], result)

    return {
        "run": _agent_run_payload(thread_id=thread_id),
        "agent_message": agent_message,
        "run_record": record,
    }


def _apply_business_scope_from_request() -> None:
    """Optional ?business=<id> or ?business=all on agent/workspace entry points."""
    raw = request.args.get("business")
    if raw is None:
        return
    if raw in ("", "all"):
        _set_selected_business_id(None)
        _ensure_chat_session()
        return
    account_id = _ensure_account_id()
    if business_store.get_business(account_id, raw):
        _set_selected_business_id(raw)
        _ensure_chat_session()


def _ctx(active: str, **extra):
    selection = _selection_context()
    auth = _auth_context()
    base = {
        "nav": NAV,
        "active_nav": active,
        "current_user": auth["current_user"],
        "account_role": auth["account_role"],
        "account_role_label": auth["account_role_label"],
        "usage_used": 0,
        "usage_quota": 0,
        "plan": None,
        "top_up_balance": 0,
        "billing_period_end": None,
        "subscription_status": "inactive",
        "cancel_at_period_end": False,
        "billing_mode": "unconfigured",
        "businesses": selection["businesses"],
        "selected_business_id": selection["selected_business_id"],
        "selected_business": selection["selected_business"],
        "business_switcher_label": selection["business_switcher_label"],
        "recent_runs": [],
        "suggested_actions": [],
        "invoices": [],
        "team_members": auth["team_members"],
        "connected_databases": [],
        "business_runs": [],
        "integration_categories": INTEGRATION_CATEGORIES,
        "integration_total": integration_count(),
        "integration_connections": [],
        "runs_today": 0,
        "runs_daily_max": run_store.RUNS_TODAY_LIMIT,
        "concurrent": 0,
        "concurrent_max": 2,
        "run_input_tokens": 0,
        "run_output_tokens": 0,
        "run_input_cap": 30_000,
        "run_output_cap": 2_000,
        "run_tool_calls": [],
        "messages": [],
        "active_thread_label": None,
    }
    base.update(_runs_dashboard_fields())
    base.update(_billing_fields())
    base.update(extra)
    return base


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id") and session.get("account_id"):
        return redirect(url_for("index"))
    error = None
    next_url = request.args.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        result = auth_store.authenticate(email, password)
        if result:
            user, membership = result
            _login_session(user, membership)
            return redirect(_safe_next_url(request.form.get("next") or next_url))
        error = "Invalid email or password."
    ctx = {"error": error, "next_url": next_url}
    ctx.update(_auth_template_context())
    copy = _site_copy(["page.auth.login_subtitle"])
    ctx["auth_subtitle"] = copy.get("page.auth.login_subtitle", "")
    return render_template("login.html", **ctx)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id") and session.get("account_id"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm = request.form.get("password_confirm", "")
        display_name = request.form.get("display_name", "")
        if password != confirm:
            error = "Passwords do not match."
        else:
            try:
                user, membership = auth_store.create_account_with_owner(
                    email=email,
                    password=password,
                    display_name=display_name,
                )
                _login_session(user, membership)
                return redirect(url_for("index"))
            except ValueError as exc:
                error = str(exc)
    ctx = {"error": error}
    ctx.update(_auth_template_context())
    copy = _site_copy(["page.auth.signup_subtitle"])
    ctx["auth_subtitle"] = copy.get("page.auth.signup_subtitle", "")
    return render_template("signup.html", **ctx)


@app.get("/auth/<provider>/start")
def login_oauth_start(provider: str):
    if session.get("user_id") and session.get("account_id"):
        return redirect(url_for("index"))
    if not login_oauth.is_login_provider(provider):
        abort(404)
    if not login_oauth.is_provider_configured(provider):
        provider_label = provider.title()
        error = f"{provider_label} sign-in is not configured on this server."
        if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
            error += (
                " Add GOOGLE_LOGIN_CLIENT_ID and GOOGLE_LOGIN_CLIENT_SECRET in "
                "Vercel → Project → Settings → Environment Variables (Production), then redeploy."
            )
        return render_template(
            "login.html",
            error=error,
            next_url="",
            **_auth_template_context(),
        )
    next_url = _safe_next_url(request.args.get("next"))
    state = login_oauth_state_store.create_state(provider=provider, next_url=next_url)
    redirect_uri = login_oauth_callback_url(provider)
    try:
        authorize_url = login_oauth.build_authorize_url(
            provider_slug=provider,
            redirect_uri=redirect_uri,
            state=state,
        )
    except ValueError as exc:
        return render_template(
            "login.html",
            error=str(exc),
            next_url=next_url,
            **_auth_template_context(),
        )
    return redirect(authorize_url)


@app.get("/auth/<provider>/callback")
def login_oauth_callback(provider: str):
    if not login_oauth.is_login_provider(provider):
        abort(404)
    oauth_error = request.args.get("error")
    if oauth_error:
        description = request.args.get("error_description") or oauth_error
        return render_template(
            "login.html",
            error=description,
            next_url="",
            **_auth_template_context(),
        )
    code = request.args.get("code", "")
    state_token = request.args.get("state", "")
    state = login_oauth_state_store.pop_state(state_token)
    if not state or state["provider"] != provider:
        return render_template(
            "login.html",
            error="Sign-in session expired or invalid. Try again.",
            next_url="",
            **_auth_template_context(),
        )
    next_url = _safe_next_url(state.get("next_url") or None)
    redirect_uri = login_oauth_callback_url(provider)
    try:
        profile = login_oauth.fetch_login_profile(
            provider_slug=provider,
            code=code,
            redirect_uri=redirect_uri,
        )
        user, membership = auth_store.login_with_oauth_profile(profile)
    except ValueError as exc:
        return render_template(
            "login.html",
            error=str(exc),
            next_url=next_url,
            **_auth_template_context(),
        )
    except RuntimeError:
        LOGGER.exception("oauth_login_failed provider=%s", provider)
        return render_template(
            "login.html",
            error="Could not complete sign-in. Try again or use email and password.",
            next_url=next_url,
            **_auth_template_context(),
        )
    _login_session(user, membership)
    return redirect(next_url)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/api/auth/me")
def api_auth_me():
    user_id = session["user_id"]
    account_id = session["account_id"]
    user = _session_user_profile(user_id)
    membership = _resolve_membership(user_id, account_id)
    if not user or not membership:
        return jsonify({"error": "authentication required"}), 401
    return jsonify(
        {
            "user": user,
            "account_id": account_id,
            "role": membership["role"],
            "role_label": membership["role_label"],
        }
    )


@app.route("/")
def index():
    if session.get("user_id") and session.get("account_id"):
        return render_template("home.html", **_ctx("home"))
    ctx = _auth_template_context()
    copy = _site_copy(
        [
            "page.start.eyebrow",
            "page.start.hero_title",
            "page.start.hero_lead",
            "page.start.hero_note",
            "page.start.cta_signup",
            "page.start.cta_signin",
        ]
    )
    ctx.update(
        start_eyebrow=copy.get("page.start.eyebrow", ""),
        start_hero_title=copy.get("page.start.hero_title", ""),
        start_hero_lead=copy.get("page.start.hero_lead", ""),
        start_hero_note=copy.get("page.start.hero_note", ""),
        start_cta_signup=copy.get("page.start.cta_signup", ""),
        start_cta_signin=copy.get("page.start.cta_signin", ""),
    )
    return render_template("start.html", **ctx)


@app.get("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html", **_legal_template_context())


@app.get("/terms-and-conditions")
def terms_and_conditions():
    return render_template("terms_and_conditions.html", **_legal_template_context())


@app.get("/licence-agreement")
def licence_agreement():
    return render_template("licence_agreement.html", **_legal_template_context())


@app.route("/businesses")
def businesses():
    return render_template("businesses.html", **_ctx("businesses"))


@app.route("/business/<business_id>")
def business_workspace(business_id: str):
    account_id = _ensure_account_id()
    biz = business_store.get_business(account_id, business_id)
    if not biz:
        abort(404)
    _set_selected_business_id(business_id)
    _ensure_chat_session()
    names = _business_names_by_id()
    business_runs = run_store.list_recent_for_display(
        account_id,
        business_id=business_id,
        business_names=names,
        limit=8,
    )
    return render_template(
        "business_workspace.html",
        **_ctx("businesses", business=biz, tab="overview", business_runs=business_runs),
    )


@app.route("/agent")
def agent():
    _apply_business_scope_from_request()
    _, thread_id = _ensure_chat_session()
    ctx = _ctx("agent")
    ctx.update(_agent_page_inspector(thread_id))
    return render_template("agent.html", **ctx)


@app.route("/data")
def data_integrations():
    catalog = catalog_for_api()
    return render_template(
        "data.html",
        **_ctx(
            "data",
            integration_categories=catalog["categories"],
            oauth_definitions=catalog["oauth"]["definitions"],
            oauth_configured=catalog["oauth"]["configured_on_server"],
            oauth_urls_wired=catalog["oauth"]["urls_wired"],
            integration_connections=_integration_connections_for_display(),
            connected_databases=_database_connections_for_display(),
        ),
    )


@app.get("/api/integrations/catalog")
def api_integrations_catalog():
    return jsonify(catalog_for_api())


@app.get("/api/integrations/oauth/providers")
def api_integration_oauth_providers():
    return jsonify({"providers": integration_oauth.list_oauth_providers()})


@app.post("/api/businesses/<business_id>/integrations/oauth/start")
def api_business_integrations_oauth_start(business_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404

    payload = request.get_json(silent=True) or {}
    provider_slug = payload.get("provider_slug")
    if not isinstance(provider_slug, str) or not provider_slug.strip():
        return jsonify({"error": "provider_slug is required"}), 400
    provider_slug = provider_slug.strip()

    if not integration_oauth.is_oauth_provider(provider_slug):
        return jsonify({"error": "OAuth is not supported for this provider"}), 400
    if not integration_oauth.is_provider_configured(provider_slug):
        return (
            jsonify(
                {
                    "error": integration_oauth.user_facing_oauth_unavailable_message(provider_slug),
                    "code": "oauth_not_configured",
                    "operator_detail": integration_oauth.operator_setup_message(provider_slug),
                }
            ),
            503,
        )

    state = oauth_state_store.create_state(
        account_id=account_id,
        business_id=business_id,
        provider_slug=provider_slug,
    )
    authorize_url = integration_oauth.build_authorize_url(
        provider_slug=provider_slug,
        redirect_uri=_oauth_redirect_uri(),
        state=state,
    )
    connection_store.connect_oauth_pending(
        account_id,
        business_id,
        provider_slug=provider_slug,
    )
    return jsonify({"authorize_url": authorize_url, "provider_slug": provider_slug})


@app.get("/integrations/oauth/callback")
def integrations_oauth_callback():
    error = request.args.get("error")
    if error:
        message = request.args.get("error_description") or error
        return redirect(url_for("data_integrations", oauth="error", oauth_message=message))

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return redirect(url_for("data_integrations", oauth="error", oauth_message="Missing code or state"))

    row = oauth_state_store.pop_state(state)
    if not row:
        return redirect(url_for("data_integrations", oauth="error", oauth_message="Invalid or expired OAuth state"))

    user_id = session.get("user_id")
    account_id = session.get("account_id")
    if not user_id or account_id != row["account_id"]:
        return redirect(url_for("login", next=request.full_path))

    try:
        credentials = integration_oauth.exchange_authorization_code(
            provider_slug=row["provider_slug"],
            code=code,
            redirect_uri=_oauth_redirect_uri(),
        )
        hint = str(credentials.pop("hint", "") or "")
        connection_store.connect_oauth_tokens(
            row["account_id"],
            row["business_id"],
            provider_slug=row["provider_slug"],
            credentials=credentials,
            credential_hint=hint,
        )
    except (ValueError, LookupError) as exc:
        return redirect(
            url_for(
                "data_integrations",
                oauth="error",
                oauth_message=str(exc)[:200],
            )
        )

    return redirect(url_for("data_integrations", oauth="connected"))


@app.get("/api/integrations/connections")
def api_integration_connections():
    account_id = _ensure_account_id()
    business_id = request.args.get("business_id")
    if business_id in ("", "all"):
        business_id = None
    elif business_id is None:
        business_id = _get_selected_business_id()
    rows = _integration_connections_for_display(business_id=business_id)
    return jsonify({"connections": [_connection_public(r) for r in rows]})


@app.get("/api/businesses/<business_id>/integrations")
def api_business_integrations_list(business_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    rows = _integration_connections_for_display(business_id=business_id)
    return jsonify({"connections": [_connection_public(r) for r in rows]})


@app.post("/api/businesses/<business_id>/integrations")
def api_business_integrations_connect(business_id: str):
    account_id = _ensure_account_id()
    payload = request.get_json(silent=True) or {}
    provider_slug = payload.get("provider_slug")
    auth_type = payload.get("auth_type") or "api_key"

    if not isinstance(provider_slug, str) or not provider_slug.strip():
        return jsonify({"error": "provider_slug is required"}), 400
    if auth_type not in ("api_key", "oauth"):
        return jsonify({"error": "auth_type must be api_key or oauth"}), 400

    try:
        if auth_type == "oauth":
            slug = provider_slug.strip()
            if not integration_oauth.is_oauth_provider(slug):
                return jsonify({"error": "OAuth is not supported for this provider"}), 400
            return (
                jsonify(
                    {
                        "error": "Use POST /api/businesses/<id>/integrations/oauth/start for OAuth",
                        "code": "use_oauth_start",
                    }
                ),
                400,
            )

        api_key = payload.get("api_key")
        if not isinstance(api_key, str):
            return jsonify({"error": "api_key is required for api_key auth"}), 400
        connection = connection_store.connect_api_key(
            account_id,
            business_id,
            provider_slug=provider_slug.strip(),
            api_key=api_key,
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    enriched = {
        **connection,
        "business_name": _business_names_by_id().get(business_id),
    }
    return jsonify({"connection": _connection_public(enriched)}), 201


@app.get("/api/databases/connections")
def api_database_connections():
    account_id = _ensure_account_id()
    business_id = request.args.get("business_id")
    if business_id in ("", "all"):
        business_id = None
    elif business_id is None:
        business_id = _get_selected_business_id()
    rows = database_store.list_connections(account_id, business_id=business_id)
    return jsonify({"connections": [database_store.connection_to_api(r) for r in rows]})


@app.get("/api/businesses/<business_id>/databases")
def api_business_databases_list(business_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    rows = database_store.list_connections(account_id, business_id=business_id)
    return jsonify({"connections": [database_store.connection_to_api(r) for r in rows]})


@app.get("/api/businesses/<business_id>/databases/<connection_id>/schema")
def api_business_database_schema(business_id: str, connection_id: str):
    account_id = _ensure_account_id()
    row = database_store.get_connection(account_id, connection_id)
    if not row or row["business_id"] != business_id:
        return jsonify({"error": "not found"}), 404
    schema = row.get("schema")
    if not schema:
        return jsonify({"error": "schema not synced"}), 404
    return jsonify({"schema": schema, "connection": database_store.connection_to_api(row)})


@app.post("/api/businesses/<business_id>/databases")
def api_business_databases_create(business_id: str):
    account_id = _ensure_account_id()
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    engine = payload.get("engine")
    host = payload.get("host") or ""
    port = payload.get("port")
    database_name = payload.get("database_name")
    username = payload.get("username") or ""
    password = payload.get("password") or ""
    access_mode = payload.get("access_mode") or "read"

    if not isinstance(name, str) or not isinstance(engine, str):
        return jsonify({"error": "name and engine are required"}), 400
    if not isinstance(database_name, str) or not database_name.strip():
        return jsonify({"error": "database_name is required"}), 400
    if port is not None and not isinstance(port, int):
        return jsonify({"error": "port must be an integer"}), 400

    try:
        row = database_store.create_connection(
            account_id,
            business_id,
            name=name,
            engine=engine,
            host=str(host),
            port=port,
            database_name=database_name,
            username=str(username),
            password=str(password),
            access_mode=str(access_mode),
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except database_introspect.DatabaseConnectionError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"connection": database_store.connection_to_api(row)}), 201


@app.post("/api/businesses/<business_id>/databases/<connection_id>/sync-schema")
def api_business_database_sync_schema(business_id: str, connection_id: str):
    account_id = _ensure_account_id()
    try:
        row = database_store.sync_schema(account_id, business_id, connection_id)
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except database_introspect.DatabaseConnectionError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"connection": database_store.connection_to_api(row)})


@app.delete("/api/businesses/<business_id>/databases/<connection_id>")
def api_business_database_delete(business_id: str, connection_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    if not database_store.delete_connection(account_id, business_id, connection_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.get("/api/businesses/<business_id>/knowledge-files")
def api_business_knowledge_files_list(business_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    rows = knowledge_store.list_files(account_id, business_id=business_id)
    return jsonify({"files": [knowledge_store.file_to_api(r) for r in rows]})


@app.post("/api/businesses/<business_id>/knowledge-files")
def api_business_knowledge_files_upload(business_id: str):
    account_id = _ensure_account_id()
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "file required"}), 400
    data = upload.read()
    try:
        record = knowledge_store.add_file(
            account_id,
            business_id,
            original_name=upload.filename,
            mime_type=upload.mimetype,
            size_bytes=len(data),
            data=data,
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 413
    return jsonify({"file": record}), 201


@app.delete("/api/businesses/<business_id>/knowledge-files/<file_id>")
def api_business_knowledge_files_delete(business_id: str, file_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    if not knowledge_store.delete_file(account_id, business_id, file_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.delete("/api/businesses/<business_id>/integrations/<connection_id>")
def api_business_integrations_disconnect(business_id: str, connection_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    if not connection_store.delete_connection(account_id, business_id, connection_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.get("/api/context")
def api_context():
    return jsonify(_selection_context())


@app.get("/api/runs")
def api_runs_list():
    account_id = _ensure_account_id()
    limit = request.args.get("limit", "20")
    try:
        limit_n = max(1, min(int(limit), 50))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    business_id = request.args.get("business_id")
    if business_id in ("", "all"):
        business_id = None
    elif business_id is not None and not isinstance(business_id, str):
        return jsonify({"error": "business_id must be a string"}), 400
    runs = run_store.list_recent_runs(
        account_id,
        business_id=business_id,
        limit=limit_n,
    )
    return jsonify(
        {
            "runs": [run_store.run_to_api_payload(r) for r in runs],
            "limits": run_limits.limits_snapshot(account_id),
        }
    )


@app.get("/api/runs/limits")
def api_run_limits():
    account_id = _ensure_account_id()
    return jsonify(run_limits.limits_snapshot(account_id))


@app.get("/api/runs/<run_id>/tool-calls")
def api_run_tool_calls(run_id: str):
    account_id = _ensure_account_id()
    run = run_store.get_run(account_id, run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    return jsonify({"tool_calls": run_store.list_tool_calls(account_id, run_id)})


@app.put("/api/businesses/selection")
def api_business_selection():
    payload = request.get_json(silent=True) or {}
    business_id = payload.get("business_id")
    account_id = _ensure_account_id()

    if business_id in (None, "", "all"):
        _set_selected_business_id(None)
    elif not isinstance(business_id, str):
        return jsonify({"error": "business_id must be a string or null"}), 400
    elif not business_store.get_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    else:
        _set_selected_business_id(business_id)

    _ensure_chat_session()
    return jsonify(_selection_context())


@app.get("/api/businesses")
def api_businesses_list():
    include_archived = request.args.get("archived") == "1"
    account_id = _ensure_account_id()
    businesses = business_store.list_businesses(account_id, include_archived=include_archived)
    return jsonify({"businesses": businesses})


@app.post("/api/businesses")
def api_businesses_create():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "name is required"}), 400
    industry = payload.get("industry")
    if industry is not None and not isinstance(industry, str):
        return jsonify({"error": "industry must be a string"}), 400
    account_id = _ensure_account_id()
    try:
        business = business_store.create_business(
            account_id,
            name=name,
            industry=industry or "",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"business": business}), 201


@app.get("/api/businesses/<business_id>")
def api_business_get(business_id: str):
    account_id = _ensure_account_id()
    business = business_store.get_business(account_id, business_id, include_archived=True)
    if not business:
        return jsonify({"error": "not found"}), 404
    return jsonify({"business": business})


@app.put("/api/businesses/<business_id>")
def api_business_update(business_id: str):
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    industry = payload.get("industry")
    archived = payload.get("archived")

    if name is not None and not isinstance(name, str):
        return jsonify({"error": "name must be a string"}), 400
    if industry is not None and not isinstance(industry, str):
        return jsonify({"error": "industry must be a string"}), 400
    if archived is not None and not isinstance(archived, bool):
        return jsonify({"error": "archived must be a boolean"}), 400
    if name is None and industry is None and archived is None:
        return jsonify({"error": "no fields to update"}), 400

    account_id = _ensure_account_id()
    try:
        business = business_store.update_business(
            account_id,
            business_id,
            name=name,
            industry=industry,
            archived=archived,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not business:
        return jsonify({"error": "not found"}), 404
    if archived is True and _get_selected_business_id() == business_id:
        _set_selected_business_id(None)
    return jsonify({"business": business})


@app.delete("/api/businesses/<business_id>")
def api_business_delete(business_id: str):
    account_id = _ensure_account_id()
    if not business_store.get_business(account_id, business_id, include_archived=True):
        return jsonify({"error": "not found"}), 404
    if not business_store.delete_business(account_id, business_id):
        return jsonify({"error": "not found"}), 404
    if _get_selected_business_id() == business_id:
        _set_selected_business_id(None)
    workspaces = _chat_workspaces_map()
    if business_id in workspaces:
        workspaces.pop(business_id, None)
        session["chat_workspaces"] = workspaces
        active_map = _active_threads_map()
        active_map.pop(business_id, None)
        session["active_thread_by_scope"] = active_map
    return jsonify({"ok": True})


@app.get("/api/search")
def api_global_search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"results": [], "scope_label": _business_switcher_label()})
    account_id = _ensure_account_id()
    _ensure_chat_session()
    scope_business_id = _get_selected_business_id()
    workspace_ids = _chat_workspace_ids_for_search()
    business_names = _business_names_by_id()
    results = global_search.search_workspace(
        query,
        workspace_ids,
        _businesses_for_search(),
        account_id=account_id,
        scope_business_id=scope_business_id,
        business_names=business_names,
    )
    return jsonify(
        {
            "results": results,
            "query": query,
            "scope_label": _business_switcher_label(),
            "scoped_business_id": scope_business_id,
        }
    )


@app.route("/billing")
def billing():
    return render_template(
        "billing.html",
        **_ctx("billing", plan_catalog=subscription_plans.catalog_for_billing()),
    )


@app.get("/api/billing/subscription")
def api_billing_subscription():
    account_id = _ensure_account_id()
    return jsonify({"subscription": subscription_store.subscription_to_api(account_id)})


@app.get("/api/billing/usage")
def api_billing_usage():
    import usage_metering

    account_id = _ensure_account_id()
    return jsonify({"usage": usage_metering.usage_snapshot(account_id)})


@app.get("/api/billing/invoices")
def api_billing_invoices():
    account_id = _ensure_account_id()
    rows = invoice_store.list_invoices(account_id)
    return jsonify({"invoices": [invoice_store.invoice_to_api(r) for r in rows]})


@app.post("/api/billing/invoices/sync")
def api_billing_invoices_sync():
    try:
        _assert_billing_owner()
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    account_id = _ensure_account_id()
    try:
        synced = square_billing.sync_invoices_from_square(account_id)
    except square_billing.SquareBillingError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"invoices": synced})


@app.post("/api/billing/checkout")
def api_billing_checkout():
    try:
        _assert_billing_owner()
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    account_id = _ensure_account_id()
    payload = request.get_json(silent=True) or {}
    plan = payload.get("plan")
    billing_interval = payload.get("billing_interval") or payload.get("interval") or "monthly"
    if not isinstance(plan, str):
        return jsonify({"error": "plan is required (starter, pro, or enterprise)"}), 400
    plan = plan.strip().lower()
    billing_interval = subscription_plans.normalize_billing_interval(
        str(billing_interval) if billing_interval else "monthly"
    )
    if not subscription_plans.is_valid_checkout(plan, billing_interval):
        return jsonify({"error": "plan must be starter, pro, or enterprise with monthly or annual billing"}), 400

    mode = square_billing.billing_mode()
    if mode == "mock":
        try:
            square_billing.mock_activate(account_id, plan, billing_interval=billing_interval)
        except square_billing.SquareBillingError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(
            {
                "mode": "mock",
                "subscription": subscription_store.subscription_to_api(account_id),
            }
        )

    if mode != "square":
        return jsonify(
            {
                "error": "Square billing is not configured. Set SQUARE_ACCESS_TOKEN and plan IDs, or BILLING_DEV_MOCK=1 for local testing.",
            }
        ), 503

    user = auth_store.get_user(session.get("user_id", ""))
    email = user.get("email") if user else None
    redirect_url = billing_checkout_return_url()

    try:
        checkout_url = square_billing.create_checkout_url(
            account_id,
            plan,
            billing_interval=billing_interval,
            redirect_url=redirect_url,
            buyer_email=email,
        )
    except square_billing.SquareBillingError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"mode": "square", "checkout_url": checkout_url})


@app.post("/api/billing/cancel")
def api_billing_cancel():
    try:
        _assert_billing_owner()
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    account_id = _ensure_account_id()
    try:
        subscription_store.cancel_at_period_end(account_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"subscription": subscription_store.subscription_to_api(account_id)})


@app.post("/webhooks/square")
def square_webhook():
    body = request.get_data()
    signature = request.headers.get("X-Square-Hmacsha256-Signature", "")
    notification_url = os.environ.get("SQUARE_WEBHOOK_NOTIFICATION_URL", "").strip()
    if not notification_url:
        notification_url = square_webhook_notification_url()

    signature_key = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "").strip()
    if signature_key:
        if not square_billing.verify_webhook_signature(body, signature, notification_url):
            return jsonify({"error": "invalid signature"}), 401
    elif os.environ.get("FLASK_ENV") == "production" or os.environ.get("APP_ENV") == "production":
        return jsonify({"error": "webhook signature key required"}), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid payload"}), 400

    try:
        square_billing.handle_webhook_payload(payload)
    except square_billing.SquareBillingError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True})


def _settings_context() -> dict:
    user_id = session.get("user_id")
    account_id = _ensure_account_id()
    if not user_id:
        abort(401)
    bundle = settings_store.settings_bundle(user_id, account_id)
    return {
        "settings_appearance": bundle["appearance"],
        "settings_agent": bundle["agent"],
        "notification_prefs": notification_store.ensure_prefs(account_id),
        "pending_team_invites": team_invite_store.list_pending_for_account(account_id)
        if session.get("role") == "owner"
        else [],
    }


@app.route("/settings")
def settings():
    return render_template("settings.html", **_ctx("settings", **_settings_context()))


@app.get("/support/contact")
def contact_support():
    intro = _site_copy(["page.support.intro"]).get("page.support.intro", "")
    return render_template(
        "contact_support.html",
        **_ctx(
            "settings",
            support_sla_hours=support_store.SUPPORT_SLA_HOURS,
            support_max_body=support_store.MAX_MESSAGE_BODY_LEN,
            support_intro=intro,
        ),
    )


@app.get("/api/support/messages")
def api_support_messages_list():
    account_id = _ensure_account_id()
    user_id = session.get("user_id")
    rows = support_store.list_messages(account_id)
    return jsonify(
        {
            "messages": [
                support_store.message_to_api(row, viewer_user_id=user_id) for row in rows
            ],
            "sla_hours": support_store.SUPPORT_SLA_HOURS,
        }
    )


@app.post("/api/support/messages")
def api_support_messages_create():
    user_id = session.get("user_id")
    account_id = _ensure_account_id()
    if not user_id:
        abort(401)
    payload = request.get_json(silent=True) or {}
    body = payload.get("body") if isinstance(payload, dict) else ""
    try:
        support_store.add_user_message(account_id=account_id, user_id=user_id, body=str(body))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    rows = support_store.list_messages(account_id)
    return jsonify(
        {
            "ok": True,
            "messages": [
                support_store.message_to_api(row, viewer_user_id=user_id) for row in rows
            ],
        }
    )


def _support_reply_token() -> str | None:
    raw = os.environ.get("SUPPORT_REPLY_TOKEN", "").strip()
    return raw or None


@app.post("/api/support/reply")
def api_support_staff_reply():
    """Operator-only: Bearer token must match SUPPORT_REPLY_TOKEN."""
    expected = _support_reply_token()
    if not expected:
        return jsonify({"error": "support replies are not configured"}), 503
    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {expected}":
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid body"}), 400
    account_id = str(payload.get("account_id") or "").strip()
    body = payload.get("body")
    if not account_id:
        return jsonify({"error": "account_id is required"}), 400
    try:
        support_store.add_support_reply(account_id=account_id, body=str(body or ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    rows = support_store.list_messages(account_id)
    return jsonify(
        {
            "ok": True,
            "messages": [support_store.message_to_api(row) for row in rows],
        }
    )


@app.get("/api/notifications")
def api_notifications_list():
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    items, unread = _notifications_feed(account_id, user_id)
    return jsonify({"notifications": items, "unread_count": unread})


@app.post("/api/notifications/read-all")
def api_notifications_read_all():
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    notification_store.mark_all_read(account_id)
    user_rows = user_notification_store.list_for_user(user_id, limit=100)
    for row in user_rows:
        if not row.get("is_read"):
            user_notification_store.mark_read(user_id, row["id"])
    _, unread = _notifications_feed(account_id, user_id)
    return jsonify({"ok": True, "unread_count": unread})


@app.post("/api/notifications/<notification_id>/read")
def api_notifications_mark_read(notification_id: str):
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    if notification_store.mark_read(account_id, notification_id):
        _, unread = _notifications_feed(account_id, user_id)
        return jsonify({"ok": True, "unread_count": unread})
    if user_notification_store.mark_read(user_id, notification_id):
        _, unread = _notifications_feed(account_id, user_id)
        return jsonify({"ok": True, "unread_count": unread})
    return jsonify({"error": "not found"}), 404


@app.delete("/api/notifications/<notification_id>")
def api_notifications_delete(notification_id: str):
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    if notification_store.delete_notification(account_id, notification_id):
        _, unread = _notifications_feed(account_id, user_id)
        return jsonify({"ok": True, "unread_count": unread})
    if user_notification_store.delete_notification(user_id, notification_id):
        _, unread = _notifications_feed(account_id, user_id)
        return jsonify({"ok": True, "unread_count": unread})
    return jsonify({"error": "not found"}), 404


@app.post("/api/notifications/delete-all")
def api_notifications_delete_all():
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    notification_store.delete_all_notifications(account_id)
    user_notification_store.delete_all(user_id)
    return jsonify({"ok": True, "deleted": True, "unread_count": 0})


@app.get("/api/team/invites")
def api_team_invites_list():
    account_id = _ensure_account_id()
    if session.get("role") != "owner":
        return jsonify({"error": "Only the account owner can view invites."}), 403
    invites = team_invite_store.list_pending_for_account(account_id)
    return jsonify({"invites": invites})


@app.post("/api/team/invites")
def api_team_invites_create():
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    payload = request.get_json(silent=True) or {}
    email = payload.get("email") or ""
    role = payload.get("role") or "operator"
    try:
        invite = team_invite_store.create_invite(
            account_id,
            email=str(email),
            role=str(role),
            invited_by_user_id=user_id,
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "invite": invite}), 201


@app.delete("/api/team/invites/<invite_id>")
def api_team_invites_cancel(invite_id: str):
    account_id = _ensure_account_id()
    user_id = session.get("user_id") or ""
    try:
        ok = team_invite_store.cancel_invite(account_id, invite_id, actor_user_id=user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True})


@app.post("/api/team/invites/<invite_id>/accept")
def api_team_invites_accept(invite_id: str):
    user_id = session.get("user_id") or ""
    if not user_id:
        return jsonify({"error": "authentication required"}), 401
    try:
        result = team_invite_store.accept_invite(invite_id, user_id=user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _apply_invite_session(result["membership"])
    account_id = session.get("account_id") or ""
    _, unread = _notifications_feed(account_id, user_id)
    return jsonify(
        {
            "ok": True,
            "membership": result["membership"],
            "redirect": url_for("index"),
            "unread_count": unread,
        }
    )


@app.post("/api/team/invites/<invite_id>/decline")
def api_team_invites_decline(invite_id: str):
    user_id = session.get("user_id") or ""
    if not user_id:
        return jsonify({"error": "authentication required"}), 401
    try:
        team_invite_store.decline_invite(invite_id, user_id=user_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    account_id = _ensure_account_id()
    _, unread = _notifications_feed(account_id, user_id)
    return jsonify({"ok": True, "unread_count": unread})


def _settings_actor() -> tuple[str, str]:
    user_id = session.get("user_id")
    account_id = session.get("account_id")
    if not user_id or not account_id:
        abort(401)
    return user_id, account_id


@app.get("/api/settings")
def api_settings_get():
    user_id, account_id = _settings_actor()
    return jsonify({"settings": settings_store.settings_bundle(user_id, account_id)})


@app.patch("/api/settings")
def api_settings_patch():
    user_id, account_id = _settings_actor()
    payload = request.get_json(silent=True) or {}

    appearance = payload.get("appearance")
    if isinstance(appearance, dict) and "theme" in appearance:
        settings_store.update_user_settings(user_id, account_id, theme=appearance["theme"])

    agent = payload.get("agent")
    if isinstance(agent, dict):
        agent_updates: dict[str, Any] = {}
        if "auto_approve_enabled" in agent:
            agent_updates["agent_auto_approve_enabled"] = bool(agent["auto_approve_enabled"])
        if "auto_approve_max_run_units" in agent:
            agent_updates["agent_auto_approve_max_run_units"] = float(
                agent["auto_approve_max_run_units"]
            )
        if "prompt_caching_enabled" in agent:
            agent_updates["agent_prompt_caching_enabled"] = bool(agent["prompt_caching_enabled"])
        if agent_updates:
            settings_store.update_user_settings(user_id, account_id, **agent_updates)

    notifications = payload.get("notifications")
    if isinstance(notifications, dict):
        notify_updates: dict[str, bool] = {}
        for key in notification_store.PREF_KEYS:
            if key in notifications:
                notify_updates[key] = bool(notifications[key])
        if notify_updates:
            notification_store.update_prefs(account_id, **notify_updates)

    return jsonify({"settings": settings_store.settings_bundle(user_id, account_id)})


@app.get("/api/settings/notifications")
def api_settings_notifications_get():
    account_id = _ensure_account_id()
    prefs = notification_store.ensure_prefs(account_id)
    return jsonify({"prefs": {k: prefs[k] for k in notification_store.PREF_KEYS}})


@app.patch("/api/settings/notifications")
def api_settings_notifications_patch():
    account_id = _ensure_account_id()
    payload = request.get_json(silent=True) or {}
    updates: dict[str, bool] = {}
    for key in notification_store.PREF_KEYS:
        if key in payload:
            updates[key] = bool(payload[key])
    prefs = notification_store.update_prefs(account_id, **updates)
    return jsonify({"prefs": {k: prefs[k] for k in notification_store.PREF_KEYS}})


@app.get("/api/settings/appearance")
def api_settings_appearance_get():
    user_id, account_id = _settings_actor()
    row = settings_store.get_user_settings(user_id, account_id)
    return jsonify({"appearance": settings_store.appearance_to_api(row)})


@app.patch("/api/settings/appearance")
def api_settings_appearance_patch():
    user_id, account_id = _settings_actor()
    payload = request.get_json(silent=True) or {}
    theme = payload.get("theme")
    if not isinstance(theme, str):
        return jsonify({"error": "theme is required"}), 400
    try:
        row = settings_store.update_user_settings(user_id, account_id, theme=theme)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"appearance": settings_store.appearance_to_api(row)})


@app.get("/api/settings/agent")
def api_settings_agent_get():
    user_id, account_id = _settings_actor()
    row = settings_store.get_user_settings(user_id, account_id)
    return jsonify({"agent": settings_store.agent_to_api(row)})


@app.patch("/api/settings/agent")
def api_settings_agent_patch():
    user_id, account_id = _settings_actor()
    payload = request.get_json(silent=True) or {}
    updates: dict[str, Any] = {}
    if "auto_approve_enabled" in payload:
        updates["agent_auto_approve_enabled"] = bool(payload["auto_approve_enabled"])
    if "auto_approve_max_run_units" in payload:
        updates["agent_auto_approve_max_run_units"] = float(payload["auto_approve_max_run_units"])
    if "prompt_caching_enabled" in payload:
        updates["agent_prompt_caching_enabled"] = bool(payload["prompt_caching_enabled"])
    try:
        row = settings_store.update_user_settings(user_id, account_id, **updates)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"agent": settings_store.agent_to_api(row)})


@app.post("/api/settings/delete-all-data")
def api_settings_delete_all_data():
    user_id, account_id = _settings_actor()
    try:
        result = account_lifecycle.purge_operational_data(account_id, user_id=user_id)
    except account_lifecycle.AccountLifecycleError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), 403
    session.pop("chat_workspaces", None)
    session.pop("active_thread_by_scope", None)
    session.pop("active_thread_id", None)
    session.pop("agent_thread_id", None)
    return jsonify(result)


@app.post("/api/settings/delete-account")
def api_settings_delete_account():
    user_id, account_id = _settings_actor()
    try:
        account_lifecycle.delete_account(account_id, user_id=user_id)
    except account_lifecycle.AccountLifecycleError as exc:
        return jsonify({"error": exc.message, "code": exc.code}), 403
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("signup")})


@app.get("/api/agent/state")
def api_agent_state():
    workspace_id, thread_id = _ensure_chat_session()
    state = chat_store.get_workspace_state(workspace_id, thread_id)
    return jsonify(_enrich_agent_state(state))


@app.post("/api/agent/threads")
def api_agent_thread_create():
    workspace_id, _ = _ensure_chat_session()
    payload = request.get_json(silent=True) or {}
    title = payload.get("title")
    if title is not None and not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    thread = chat_store.create_side_thread(workspace_id, title)
    _persist_active_thread(thread["id"])
    state = chat_store.get_workspace_state(workspace_id, thread["id"])
    return jsonify(_enrich_agent_state(state)), 201


@app.put("/api/agent/threads/<thread_id>")
def api_agent_thread_rename(thread_id: str):
    workspace_id, _ = _ensure_chat_session()
    payload = request.get_json(silent=True) or {}
    title = payload.get("title")
    if title is None or not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    meta = chat_store.rename_thread(workspace_id, thread_id, title)
    if not meta:
        return jsonify({"error": "not found"}), 404
    active = _active_threads_map().get(_chat_scope_key()) or thread_id
    state = chat_store.get_workspace_state(workspace_id, active)
    return jsonify(_enrich_agent_state(state))


@app.delete("/api/agent/threads/<thread_id>")
def api_agent_thread_delete(thread_id: str):
    workspace_id, active = _ensure_chat_session()
    if not chat_store.delete_side_thread(workspace_id, thread_id):
        return jsonify({"error": "not found or not deletable"}), 404
    if active == thread_id:
        threads = chat_store.list_workspace_threads(workspace_id)
        main = next((t for t in threads if t.get("kind") == "main"), threads[0])
        _persist_active_thread(main["id"])
        active = main["id"]
    state = chat_store.get_workspace_state(workspace_id, active)
    return jsonify(_enrich_agent_state(state))


@app.post("/api/agent/main/clear")
def api_agent_main_clear():
    workspace_id, active = _ensure_chat_session()
    meta = chat_store.clear_main_thread(workspace_id)
    if not meta:
        return jsonify({"error": "main chat not found"}), 404
    state = chat_store.get_workspace_state(workspace_id, active)
    return jsonify(_enrich_agent_state(state))


@app.post("/api/agent/threads/<thread_id>/activate")
def api_agent_thread_activate(thread_id: str):
    workspace_id, _ = _ensure_chat_session()
    threads = chat_store.list_workspace_threads(workspace_id)
    if not any(t["id"] == thread_id for t in threads):
        return jsonify({"error": "not found"}), 404
    _persist_active_thread(thread_id)
    state = chat_store.get_workspace_state(workspace_id, thread_id)
    return jsonify(_enrich_agent_state(state))


@app.post("/api/agent/runs/<run_id>/focus")
def api_agent_run_focus(run_id: str):
    account_id = _ensure_account_id()
    run = run_store.get_run(account_id, run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    session["last_agent_run_id"] = run_id
    if run.get("business_id"):
        _set_selected_business_id(run["business_id"])
        _ensure_chat_session()
    if run.get("thread_id"):
        _persist_active_thread(run["thread_id"])
    return jsonify({"ok": True, "run_id": run_id})


@app.put("/api/agent/draft")
def api_agent_draft():
    thread_id = _active_thread_id()
    payload = request.get_json(silent=True) or {}
    body = payload.get("body")
    if body is None or not isinstance(body, str):
        return jsonify({"error": "body must be a string"}), 400
    chat_store.set_draft_body(thread_id, body)
    return jsonify({"draft": chat_store.get_draft(thread_id)})


@app.post("/api/agent/draft/files")
def api_agent_draft_file():
    thread_id = _active_thread_id()
    upload = request.files.get("file")
    if not upload or not upload.filename:
        return jsonify({"error": "file required"}), 400
    data = upload.read()
    try:
        record = chat_store.add_draft_file(
            thread_id,
            original_name=upload.filename,
            mime_type=upload.mimetype,
            size_bytes=len(data),
            data=data,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 413
    return jsonify({"file": record, "draft": chat_store.get_draft(thread_id)}), 201


@app.delete("/api/agent/draft/files/<int:file_id>")
def api_agent_draft_file_delete(file_id: int):
    thread_id = _active_thread_id()
    if not chat_store.remove_draft_file(thread_id, file_id):
        return jsonify({"error": "not found"}), 404
    return jsonify({"draft": chat_store.get_draft(thread_id)})


@app.post("/api/agent/messages")
def api_agent_message():
    thread_id = _active_thread_id()
    payload = request.get_json(silent=True) or {}
    content = (payload.get("content") or "").strip()
    draft = chat_store.get_draft(thread_id)
    if not content and not draft["files"]:
        return jsonify({"error": "message or attachments required"}), 400

    account_id = _ensure_account_id()
    summary = content.strip() if content.strip() else "File attachment"
    try:
        run_limits.assert_can_start(account_id)
    except RunLimitError as exc:
        run_store.record_blocked_run(
            account_id=account_id,
            user_id=session.get("user_id"),
            business_id=_get_selected_business_id(),
            thread_id=thread_id,
            summary=summary,
            error_code=exc.code,
        )
        import notification_events

        notification_events.notify_run_blocked(
            account_id,
            error_code=exc.code,
            summary=summary,
        )
        limits = run_limits.limits_snapshot(account_id)
        return (
            jsonify(
                {
                    "error": exc.message,
                    "code": exc.code,
                    "limits": limits,
                }
            ),
            429,
        )

    message = chat_store.create_user_message(thread_id, content)
    turn = _execute_agent_turn(thread_id, trigger_summary=summary)
    workspace_id, _ = _ensure_chat_session()
    state = chat_store.get_workspace_state(workspace_id, thread_id)
    return jsonify(
        {
            "message": message,
            "draft": chat_store.get_draft(thread_id),
            "agent_message": turn["agent_message"],
            "run": turn["run"],
            "messages": state["messages"],
        }
    )


@app.post("/api/agent/messages/stream")
def api_agent_message_stream():
    thread_id = _active_thread_id()
    payload = request.get_json(silent=True) or {}
    content = (payload.get("content") or "").strip()
    draft = chat_store.get_draft(thread_id)
    if not content and not draft["files"]:
        return jsonify({"error": "message or attachments required"}), 400

    account_id = _ensure_account_id()
    summary = content.strip() if content.strip() else "File attachment"
    try:
        run_limits.assert_can_start(account_id)
    except RunLimitError as exc:
        run_store.record_blocked_run(
            account_id=account_id,
            user_id=session.get("user_id"),
            business_id=_get_selected_business_id(),
            thread_id=thread_id,
            summary=summary,
            error_code=exc.code,
        )
        import notification_events

        notification_events.notify_run_blocked(
            account_id,
            error_code=exc.code,
            summary=summary,
        )
        limits = run_limits.limits_snapshot(account_id)
        return (
            jsonify(
                {
                    "error": exc.message,
                    "code": exc.code,
                    "limits": limits,
                }
            ),
            429,
        )

    user_message = chat_store.create_user_message(thread_id, content)
    run = run_store.begin_chat_run(
        account_id=account_id,
        user_id=session.get("user_id"),
        business_id=_get_selected_business_id(),
        thread_id=thread_id,
        summary=summary,
    )
    run_id = run["id"]
    session["last_agent_run_id"] = run_id
    cancel_event = agent_executor.attach_stream_cancel(run_id)

    scope_label = _business_switcher_label()
    business_name = _business_name_for_agent()

    def event_stream():
        accumulated: list[str] = []
        final_result = None
        persisted = False
        try:
            yield _agent_sse(
                {
                    "type": "start",
                    "run_id": run_id,
                    "message": user_message,
                }
            )
            for event in agent_executor.stream_generate_reply(
                thread_id,
                scope_label=scope_label,
                business_name=business_name,
                account_id=account_id,
                business_id=_get_selected_business_id(),
                cancel_event=cancel_event,
            ):
                if event.get("event") == "delta":
                    piece = event.get("text") or ""
                    accumulated.append(piece)
                    yield _agent_sse({"type": "delta", "text": piece})
                elif event.get("event") == "done":
                    final_result = event.get("result")
            if final_result is None:
                final_result = agent_executor.AgentRunResult(
                    status="error",
                    content="Stream ended without a result.",
                    error_code="http_error",
                )
            _persist_agent_run_result(thread_id, account_id, run_id, final_result)
            persisted = True
            yield _agent_sse({"type": "done"})
        except GeneratorExit:
            if not persisted:
                partial = "".join(accumulated)
                _persist_agent_run_result(
                    thread_id,
                    account_id,
                    run_id,
                    agent_executor.AgentRunResult(
                        status="error",
                        content=partial,
                        error_code="cancelled",
                    ),
                )
            raise
        finally:
            agent_executor.detach_stream_cancel(run_id)

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/agent/runs/<run_id>/cancel")
def api_agent_run_cancel(run_id: str):
    account_id = _ensure_account_id()
    run = run_store.get_run(account_id, run_id)
    if not run or run.get("status") != "running":
        return jsonify({"error": "not found"}), 404
    agent_executor.request_stream_cancel(run_id)
    return jsonify({"ok": True})


@app.put("/api/agent/messages/<int:message_id>")
def api_agent_message_update(message_id: int):
    thread_id = _active_thread_id()
    payload = request.get_json(silent=True) or {}
    content = payload.get("content")
    if content is None or not isinstance(content, str):
        return jsonify({"error": "content must be a string"}), 400
    message = chat_store.update_user_message(thread_id, message_id, content)
    if not message:
        return jsonify({"error": "not found or not editable"}), 404
    return jsonify({"message": message})


@app.delete("/api/agent/messages/<int:message_id>")
def api_agent_message_delete(message_id: int):
    thread_id = _active_thread_id()
    if not chat_store.delete_user_message(thread_id, message_id):
        return jsonify({"error": "not found or not deletable"}), 404
    state = chat_store.get_thread_state(thread_id)
    return jsonify({"messages": state["messages"]})


@app.route("/admin")
def admin_shortcut():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin.admin_dashboard"))
    return redirect(url_for("admin.admin_login"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=APP_CONFIG.debug)
