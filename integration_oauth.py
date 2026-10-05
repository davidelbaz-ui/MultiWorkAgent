"""OAuth 2.0 authorize + token exchange for integration providers."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import integration_oauth_hints
from integration_oauth_registry import OAUTH_PROVIDERS, OAuthProviderTemplate


def list_oauth_providers() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for provider in OAUTH_PROVIDERS.values():
        items.append(provider_public(provider))
    return items


def provider_public(provider: OAuthProviderTemplate) -> dict[str, Any]:
    return {
        "provider_slug": provider.slug,
        "display_name": provider.display_name,
        "auth_type": "oauth",
        "configured": is_provider_configured(provider.slug),
        "scopes": provider.scopes,
    }


def get_oauth_provider(slug: str) -> OAuthProviderTemplate | None:
    return OAUTH_PROVIDERS.get(slug)


def is_oauth_provider(slug: str) -> bool:
    return slug in OAUTH_PROVIDERS


def is_provider_configured(slug: str) -> bool:
    provider = get_oauth_provider(slug)
    if not provider:
        return False
    client_id = os.environ.get(provider.client_id_env, "").strip()
    client_secret = os.environ.get(provider.client_secret_env, "").strip()
    if not client_id or not client_secret:
        return False
    if slug == "vercel" and not os.environ.get("VERCEL_OAUTH_INTEGRATION_SLUG", "").strip():
        return False
    return True


def operator_setup_message(slug: str) -> str | None:
    provider = get_oauth_provider(slug)
    if not provider:
        return None
    return f"Set {provider.client_id_env} and {provider.client_secret_env} on the server."


def user_facing_oauth_unavailable_message(slug: str) -> str:
    provider = get_oauth_provider(slug)
    name = provider.display_name if provider else "This provider"
    return (
        f"{name} OAuth is not enabled on this server yet. "
        "Connect with an API key instead, or contact the person who runs MultiWorkAgent."
    )


def _client_credentials(provider: OAuthProviderTemplate) -> tuple[str, str]:
    client_id = os.environ.get(provider.client_id_env, "").strip()
    client_secret = os.environ.get(provider.client_secret_env, "").strip()
    if not client_id or not client_secret:
        raise ValueError(user_facing_oauth_unavailable_message(provider.slug))
    return client_id, client_secret


def build_authorize_url(*, provider_slug: str, redirect_uri: str, state: str) -> str:
    provider = get_oauth_provider(provider_slug)
    if not provider:
        raise ValueError("OAuth is not supported for this provider")
    if not provider.urls_configured or not provider.authorize_url.strip():
        raise ValueError(
            f"{provider.display_name} OAuth URLs are not wired in integration_oauth_registry.py yet. "
            "Use an API key for now."
        )
    _client_credentials(provider)

    if provider_slug == "vercel":
        integration_slug = os.environ.get("VERCEL_OAUTH_INTEGRATION_SLUG", "").strip()
        if not integration_slug:
            raise ValueError(
                "Set VERCEL_OAUTH_INTEGRATION_SLUG from Vercel → Integrations → your integration slug."
            )
        params = {"state": state}
        return (
            f"https://vercel.com/integrations/{urllib.parse.quote(integration_slug)}/new?"
            f"{urllib.parse.urlencode(params)}"
        )

    client_id, _ = _client_credentials(provider)
    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    }
    if provider.scopes:
        params["scope"] = provider.scopes
    params.update(provider.authorize_extra)
    query = urllib.parse.urlencode(params)
    return f"{provider.authorize_url}?{query}"


def exchange_authorization_code(
    *,
    provider_slug: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    provider = get_oauth_provider(provider_slug)
    if not provider:
        raise ValueError("OAuth is not supported for this provider")
    if not provider.urls_configured or not provider.token_url.strip():
        raise ValueError(
            f"{provider.display_name} OAuth URLs are not wired in integration_oauth_registry.py yet."
        )
    client_id, client_secret = _client_credentials(provider)

    body_params = {
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    headers: dict[str, str] = {"Accept": "application/json"}

    if provider.token_auth == "basic":
        token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(body_params).encode("utf-8")
    elif provider.token_auth == "json":
        body_params["client_id"] = client_id
        body_params["client_secret"] = client_secret
        headers["Content-Type"] = "application/json"
        body = json.dumps(body_params).encode("utf-8")
    else:
        body_params["client_id"] = client_id
        body_params["client_secret"] = client_secret
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urllib.parse.urlencode(body_params).encode("utf-8")

    req = urllib.request.Request(provider.token_url, data=body, method="POST", headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ValueError(f"Token exchange failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Token exchange failed: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = dict(urllib.parse.parse_qsl(raw))

    if data.get("error"):
        raise ValueError(str(data.get("error_description") or data.get("error")))

    access_token = data.get("access_token")
    if not access_token and isinstance(data.get("authed_user"), dict):
        access_token = data["authed_user"].get("access_token")
    if not access_token:
        raise ValueError("Provider did not return an access token")

    credentials: dict[str, Any] = {
        "access_token": access_token,
        "token_type": data.get("token_type") or "bearer",
        "scope": data.get("scope"),
    }
    if data.get("refresh_token"):
        credentials["refresh_token"] = data["refresh_token"]
    if data.get("expires_in") is not None:
        credentials["expires_in"] = data.get("expires_in")
    if data.get("realmId"):
        credentials["realm_id"] = data.get("realmId")
    if data.get("instance_url"):
        credentials["instance_url"] = data.get("instance_url")

    hint = integration_oauth_hints.fetch_credential_hint(provider, access_token)
    credentials["hint"] = hint
    return credentials


def fetch_credential_hint(provider_slug: str, access_token: str) -> str:
    provider = get_oauth_provider(provider_slug)
    if not provider:
        return "oauth"
    return integration_oauth_hints.fetch_credential_hint(provider, access_token)
