"""Fetch human-readable credential hints after OAuth token exchange."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from integration_oauth_registry import OAuthProviderTemplate


def fetch_credential_hint(provider: OAuthProviderTemplate, access_token: str) -> str:
    slug = provider.slug
    try:
        if slug == "github":
            user = _json_get(
                "https://api.github.com/user",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": "MultiWorkAgent",
                },
            )
            login = user.get("login") or user.get("name") or "github"
            return f"github · {login}"

        if slug.startswith("google") or slug == "google-workspace-gmail-docs-drive-sheets-calendar":
            user = _json_get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            email = user.get("email") or user.get("name") or "google"
            return f"google · {email}"

        if slug == "gitlab":
            user = _json_get(
                "https://gitlab.com/api/v4/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            username = user.get("username") or user.get("name") or "gitlab"
            return f"gitlab · {username}"

        if slug == "slack":
            data = _json_get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            team = data.get("team") or data.get("team_id") or "slack"
            user = data.get("user") or ""
            return f"slack · {team}" + (f" ({user})" if user else "")

        if slug == "microsoft-365-outlook-onedrive-sharepoint-excel":
            user = _json_get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            label = user.get("userPrincipalName") or user.get("displayName") or "microsoft"
            return f"microsoft · {label}"
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError):
        pass
    return f"{provider.display_name.lower()} · connected"


def _json_get(url: str, *, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data
