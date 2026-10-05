"""Environment-driven application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

DEV_SECRET_PLACEHOLDER = "dev-change-me-in-production"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    debug: bool
    secret_key: str
    session_cookie_secure: bool
    session_cookie_httponly: bool
    session_cookie_samesite: str
    trust_proxy: bool
    rate_limit_enabled: bool
    rate_limit_login_per_minute: int
    rate_limit_signup_per_minute: int
    rate_limit_api_per_minute: int
    log_level: str
    log_json: bool


def is_production_env(app_env: str) -> bool:
    return app_env.strip().lower() in ("production", "prod")


def is_vercel_runtime() -> bool:
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def load_app_config() -> AppConfig:
    app_env = os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "development"
    production = is_production_env(app_env)
    on_vercel = is_vercel_runtime()
    secret_key = os.environ.get("FLASK_SECRET_KEY", DEV_SECRET_PLACEHOLDER).strip()

    if production and (not secret_key or secret_key == DEV_SECRET_PLACEHOLDER):
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set to a strong random value when APP_ENV=production"
        )

    secure_cookies = (
        _env_bool("SESSION_COOKIE_SECURE", production)
        or _env_bool("FORCE_HTTPS", False)
        or on_vercel
    )

    return AppConfig(
        app_env=app_env,
        debug=_env_bool("FLASK_DEBUG", not production and not on_vercel),
        secret_key=secret_key,
        session_cookie_secure=secure_cookies,
        session_cookie_httponly=True,
        session_cookie_samesite=os.environ.get("SESSION_COOKIE_SAMESITE", "Lax").strip()
        or "Lax",
        trust_proxy=_env_bool("TRUST_PROXY", on_vercel),
        rate_limit_enabled=_env_bool("RATE_LIMIT_ENABLED", True),
        rate_limit_login_per_minute=_env_int("RATE_LIMIT_LOGIN_PER_MINUTE", 10),
        rate_limit_signup_per_minute=_env_int("RATE_LIMIT_SIGNUP_PER_MINUTE", 5),
        rate_limit_api_per_minute=_env_int("RATE_LIMIT_API_PER_MINUTE", 240),
        log_level=os.environ.get("LOG_LEVEL", "INFO" if production else "DEBUG").upper(),
        log_json=_env_bool("LOG_JSON", production),
    )


def apply_flask_config(app, config: AppConfig) -> None:
    app.config["SECRET_KEY"] = config.secret_key
    app.config["SESSION_COOKIE_SECURE"] = config.session_cookie_secure
    app.config["SESSION_COOKIE_HTTPONLY"] = config.session_cookie_httponly
    app.config["SESSION_COOKIE_SAMESITE"] = config.session_cookie_samesite
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
        days=_env_int("SESSION_LIFETIME_DAYS", 30)
    )
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config["APP_ENV"] = config.app_env
    app.config["DEBUG"] = config.debug
    app.config["MAX_CONTENT_LENGTH"] = _env_int("MAX_UPLOAD_BYTES", 16 * 1024 * 1024)


def validate_production_secrets(config: AppConfig) -> list[str]:
    """Return warning messages for weak production configuration."""
    warnings: list[str] = []
    if not is_production_env(config.app_env):
        return warnings
    if not os.environ.get("INTEGRATION_ENCRYPTION_KEY", "").strip():
        warnings.append(
            "INTEGRATION_ENCRYPTION_KEY is not set; integration credentials derive from FLASK_SECRET_KEY"
        )
    from pg_storage import ephemeral_local_storage, postgres_configured

    if is_production_env(config.app_env) and not postgres_configured():
        warnings.append(
            "DATABASE_URL is not set; businesses, chats, and logins will not persist. "
            "Use postgresql://user:password@host:5432/dbname (Vercel Postgres, Neon, etc.)."
        )
    elif is_production_env(config.app_env) and ephemeral_local_storage():
        warnings.append("DATABASE_URL is missing on this host; data will not persist.")
    return warnings
