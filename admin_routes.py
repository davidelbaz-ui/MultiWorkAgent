"""Operator console at /admin on the main app (production + local)."""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import admin_auth
import admin_log_buffer
import admin_stats
import app_logging
import app_state
import http_rate_limit
import site_settings_store
import support_store

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
_ADMIN_LOGGER = logging.getLogger("bma")


def _db_ready() -> bool:
    if current_app.config.get("DB_READY") is not None:
        return bool(current_app.config.get("DB_READY"))
    return app_state.DB_READY


def _db_error() -> str | None:
    err = current_app.config.get("DB_INIT_ERROR")
    if err is not None:
        return str(err) if err else None
    return app_state.DB_INIT_ERROR


@admin_bp.before_request
def admin_gate():
    try:
        endpoint = request.endpoint or ""

        if endpoint == "admin.admin_ping":
            return None

        if not _db_ready():
            if endpoint == "admin.admin_login":
                return None
            return (
                render_template(
                    "admin/db_required.html",
                    db_error=_db_error(),
                ),
                503,
            )

        if not admin_auth.admin_configured():
            if endpoint == "admin.admin_login":
                return None
            return render_template("admin/not_configured.html"), 503

        if endpoint in {"admin.admin_login", "admin.admin_health", "admin.admin_ping"}:
            return None

        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.admin_login", next=request.path))

        g.admin_email = session.get("admin_email") or admin_auth.admin_email()
        return None
    except Exception:
        _ADMIN_LOGGER.exception("admin_gate_failed path=%s", request.path)
        raise


@admin_bp.get("/ping")
def admin_ping():
    return {"ok": True, "admin": admin_auth.admin_configured(), "db": _db_ready()}


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin.admin_dashboard"))
    error = None
    if request.method == "POST":
        remote = request.headers.get("X-Forwarded-For", request.remote_addr) or ""
        if "," in remote:
            remote = remote.split(",", 1)[0].strip()
        if not http_rate_limit.allow("auth:admin", remote, max_events=10):
            return render_template(
                "admin/login.html",
                error="Too many attempts. Wait a minute and try again.",
            ), 429
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if admin_auth.verify_admin_login(email, password):
            session.clear()
            session["admin_authenticated"] = True
            session["admin_email"] = admin_auth.admin_email()
            session.permanent = True
            app_logging.log_event(
                _ADMIN_LOGGER,
                "admin_login_ok",
                email=admin_auth.admin_email(),
                remote_addr=remote,
            )
            dest = request.args.get("next") or request.form.get("next") or url_for(
                "admin.admin_dashboard"
            )
            if not dest.startswith("/admin"):
                dest = url_for("admin.admin_dashboard")
            return redirect(dest)
        error = "Invalid email or password."
    return render_template("admin/login.html", error=error)


@admin_bp.post("/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    session.pop("admin_email", None)
    return redirect(url_for("admin.admin_login"))


@admin_bp.get("/")
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        counts=admin_stats.platform_counts(),
        db=admin_stats.database_status(),
        support_open=support_store.list_inbox(limit=8, status="open"),
    )


@admin_bp.get("/support")
def admin_support_inbox():
    status = request.args.get("status", "").strip() or None
    threads = support_store.list_inbox(limit=100, status=status)
    return render_template(
        "admin/support_inbox.html",
        threads=threads,
        filter_status=status or "",
    )


@admin_bp.get("/support/<account_id>")
def admin_support_thread(account_id: str):
    rows = support_store.list_messages(account_id)
    thread = support_store.get_or_create_thread(account_id)
    meta = next(
        (t for t in support_store.list_inbox(limit=200) if t["account_id"] == account_id),
        None,
    )
    return render_template(
        "admin/support_thread.html",
        account_id=account_id,
        thread=thread,
        meta=meta,
        messages=[support_store.message_to_api(row) for row in rows],
        sla_hours=support_store.SUPPORT_SLA_HOURS,
    )


@admin_bp.post("/support/<account_id>/reply")
def admin_support_reply(account_id: str):
    body = request.form.get("body", "")
    try:
        support_store.add_support_reply(account_id=account_id, body=body)
        flash("Reply sent.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.admin_support_thread", account_id=account_id))


@admin_bp.post("/support/<account_id>/status")
def admin_support_status(account_id: str):
    status = request.form.get("status", "open")
    try:
        support_store.set_thread_status(account_id, status)
        flash(f"Thread marked {status}.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.admin_support_thread", account_id=account_id))


@admin_bp.get("/logs")
def admin_logs():
    level = request.args.get("level", "").strip() or None
    rows = admin_log_buffer.recent_logs(limit=250, level=level)
    return render_template("admin/logs.html", logs=rows, filter_level=level or "")


@admin_bp.get("/system")
def admin_system():
    from app_urls import public_app_base_url

    return render_template(
        "admin/system.html",
        db=admin_stats.database_status(),
        counts=admin_stats.platform_counts(),
        main_app_url=public_app_base_url(),
    )


@admin_bp.context_processor
def admin_layout_context():
    from app_urls import public_app_base_url

    return {"public_site_url": public_app_base_url()}


@admin_bp.get("/pages")
def admin_pages():
    return render_template(
        "admin/pages.html",
        sections=site_settings_store.admin_sections(),
    )


@admin_bp.post("/pages")
def admin_pages_save():
    site_settings_store.apply_form_values(request.form, updated_by=g.admin_email)
    flash("Page settings saved.", "success")
    return redirect(url_for("admin.admin_pages"))


@admin_bp.get("/health")
def admin_health():
    return (
        {
            "ok": app_state.DB_READY,
            "admin": admin_auth.admin_configured(),
        },
        200 if app_state.DB_READY else 503,
    )
