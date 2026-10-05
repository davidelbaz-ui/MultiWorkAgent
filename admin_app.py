"""Local operator console — run separately on http://127.0.0.1:8000 (not deployed to Vercel)."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass

from flask import (
    Flask,
    abort,
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
import site_settings_store
import support_store
from app_config import apply_flask_config, load_app_config

# Bootstrap main app stores (Postgres, migrations).
import app as main_app  # noqa: F401

APP_CONFIG = load_app_config()
admin = Flask(__name__, static_folder="static", template_folder="templates")
apply_flask_config(admin, APP_CONFIG)
admin.secret_key = APP_CONFIG.secret_key
LOGGER = app_logging.configure_logging(APP_CONFIG)

ADMIN_HOST = os.environ.get("ADMIN_HOST", "127.0.0.1").strip() or "127.0.0.1"
ADMIN_PORT = int(os.environ.get("ADMIN_PORT", "8000"))


def _db_ready() -> bool:
    return main_app.DB_READY


def _require_admin():
    if not session.get("admin_authenticated"):
        return redirect(url_for("admin_login", next=request.path))
    g.admin_email = session.get("admin_email") or admin_auth.admin_email()
    return None


@admin.before_request
def admin_gate():
    if not _db_ready():
        if request.endpoint == "admin_login":
            return None
        return render_template(
            "admin/db_required.html",
            db_error=main_app.DB_INIT_ERROR,
        ), 503
    if not admin_auth.admin_configured():
        if request.endpoint == "admin_login":
            return None
        return render_template("admin/not_configured.html"), 503
    endpoint = request.endpoint or ""
    if endpoint in {"admin_login", "static", "admin_health"}:
        return None
    return _require_admin()


@admin.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if admin_auth.verify_admin_login(email, password):
            session.clear()
            session["admin_authenticated"] = True
            session["admin_email"] = admin_auth.admin_email()
            session.permanent = True
            dest = request.args.get("next") or url_for("admin_dashboard")
            return redirect(dest)
        error = "Invalid email or password."
    return render_template("admin/login.html", error=error)


@admin.post("/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@admin.get("/")
def admin_dashboard():
    return render_template(
        "admin/dashboard.html",
        counts=admin_stats.platform_counts(),
        db=admin_stats.database_status(),
        support_open=support_store.list_inbox(limit=8, status="open"),
    )


@admin.get("/support")
def admin_support_inbox():
    status = request.args.get("status", "").strip() or None
    threads = support_store.list_inbox(limit=100, status=status)
    return render_template(
        "admin/support_inbox.html",
        threads=threads,
        filter_status=status or "",
    )


@admin.get("/support/<account_id>")
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


@admin.post("/support/<account_id>/reply")
def admin_support_reply(account_id: str):
    body = request.form.get("body", "")
    try:
        support_store.add_support_reply(account_id=account_id, body=body)
        flash("Reply sent.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_support_thread", account_id=account_id))


@admin.post("/support/<account_id>/status")
def admin_support_status(account_id: str):
    status = request.form.get("status", "open")
    try:
        support_store.set_thread_status(account_id, status)
        flash(f"Thread marked {status}.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_support_thread", account_id=account_id))


@admin.get("/logs")
def admin_logs():
    level = request.args.get("level", "").strip() or None
    rows = admin_log_buffer.recent_logs(limit=250, level=level)
    return render_template("admin/logs.html", logs=rows, filter_level=level or "")


@admin.get("/system")
def admin_system():
    return render_template(
        "admin/system.html",
        db=admin_stats.database_status(),
        counts=admin_stats.platform_counts(),
        main_app_url=os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000"),
    )


@admin.get("/pages")
def admin_pages():
    return render_template("admin/pages.html", pages=site_settings_store.list_all())


@admin.post("/pages")
def admin_pages_save():
    values = {}
    for item in site_settings_store.PAGE_DEFINITIONS:
        key = item["key"]
        if key in request.form:
            values[key] = request.form.get(key, "")
    site_settings_store.update_values(values, updated_by=g.admin_email)
    flash("Page settings saved.", "success")
    return redirect(url_for("admin_pages"))


@admin.get("/health")
def admin_health():
    return {"ok": _db_ready(), "admin": admin_auth.admin_configured()}, 200 if _db_ready() else 503


if __name__ == "__main__":
    if not admin_auth.admin_configured():
        LOGGER.warning(
            "admin_not_configured Set ADMIN_EMAIL and ADMIN_PASSWORD in .env then restart."
        )
    LOGGER.info("admin_listen http://%s:%s", ADMIN_HOST, ADMIN_PORT)
    admin.run(host=ADMIN_HOST, port=ADMIN_PORT, debug=APP_CONFIG.debug)
