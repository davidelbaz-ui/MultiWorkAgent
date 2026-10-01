"""OAuth 2.0 / OpenID Connect for app login (Google Cloud)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

LOGIN_PROVIDERS = frozenset({"google"})


@dataclass(frozen=True)
class LoginOAuthProvider:
    slug: str
    display_name: str
    authorize_url: str
    token_url: str
    scopes: str
    client_id_env: str
    client_secret_env: str


GOOGLE = LoginOAuthProvider(
    slug="google",
    display_name="Google",
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    token_url="https://oauth2.googleapis.com/token",
    scopes="openid email profile",
    client_id_env="GOOGLE_LOGIN_CLIENT_ID",
    client_secret_env="GOOGLE_LOGIN_CLIENT_SECRET",
)

_PROVIDERS: dict[str, LoginOAuthProvider] = {
    GOOGLE.slug: GOOGLE,
}


def _provider(slug: str) -> LoginOAuthProvider | None:
    return _PROVIDERS.get(slug)


def is_login_provider(slug: str) -> bool:
    return slug in LOGIN_PROVIDERS and slug in _PROVIDERS


def is_provider_configured(slug: str) -> bool:
    provider = _provider(slug)
    if not provider:
        return False
    client_id = os.environ.get(provider.client_id_env, "").strip()
    client_secret = os.environ.get(provider.client_secret_env, "").strip()
    return bool(client_id and client_secret)


def configured_login_providers() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for slug in ("google",):
        provider = _PROVIDERS[slug]
        items.append(
            {
                "slug": slug,
                "display_name": provider.display_name,
                "configured": is_provider_configured(slug),
            }
        )
    return items


def _client_credentials(provider: LoginOAuthProvider) -> tuple[str, str]:
    client_id = os.environ.get(provider.client_id_env, "").strip()
    client_secret = os.environ.get(provider.client_secret_env, "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            f"{provider.display_name} sign-in is not configured. "
            f"Set {provider.client_id_env} and {provider.client_secret_env}."
        )
    return client_id, client_secret


def build_authorize_url(*, provider_slug: str, redirect_uri: str, state: str) -> str:
    provider = _provider(provider_slug)
    if not provider:
        raise ValueError("Unknown login provider")
    client_id, _ = _client_credentials(provider)
    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": provider.scopes,
        "state": state,
    }
    if provider.slug == GOOGLE.slug:
        params["prompt"] = "select_account"
    return f"{provider.authorize_url}?{urllib.parse.urlencode(params)}"


def _exchange_code(
    *,
    provider: LoginOAuthProvider,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    client_id, client_secret = _client_credentials(provider)
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        provider.token_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"Token exchange failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Token exchange failed: {exc.reason}") from exc

    data = json.loads(raw)
    if data.get("error"):
        raise ValueError(str(data.get("error_description") or data.get("error")))
    access_token = data.get("access_token")
    if not access_token:
        raise ValueError("Provider did not return an access token")
    return data


def _http_get_json(url: str, access_token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "MultiWorkAgent",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_login_profile(*, provider_slug: str, code: str, redirect_uri: str) -> dict[str, Any]:
    """Return normalized profile: provider, subject, email, display_name, email_verified."""
    provider = _provider(provider_slug)
    if not provider:
        raise ValueError("Unknown login provider")
    token_data = _exchange_code(provider=provider, code=code, redirect_uri=redirect_uri)
    access_token = str(token_data["access_token"])

    if provider.slug == GOOGLE.slug:
        user = _http_get_json("https://openidconnect.googleapis.com/v1/userinfo", access_token)
        email = (user.get("email") or "").strip().lower()
        if not email:
            raise ValueError("Google did not return an email address")
        verified = bool(user.get("email_verified"))
        if not verified:
            raise ValueError("Google email is not verified")
        subject = str(user.get("sub") or "")
        if not subject:
            raise ValueError("Google did not return a user id")
        name = (user.get("name") or user.get("given_name") or "").strip()
        return {
            "provider": "google",
            "subject": subject,
            "email": email,
            "display_name": name,
            "email_verified": True,
        }

    raise ValueError("Unsupported login provider")
