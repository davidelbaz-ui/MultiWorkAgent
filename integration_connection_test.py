"""Live connection tests for stored integration credentials (read-only API probes)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class IntegrationTestResult:
    ok: bool
    probe: str
    message: str
    detail: str | None = None
    http_status: int | None = None

    def to_api(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "probe": self.probe,
            "message": self.message,
            "detail": self.detail,
            "http_status": self.http_status,
        }


def _token(credentials: dict[str, Any]) -> str | None:
    for key in ("access_token", "api_key"):
        value = credentials.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str],
    body: bytes | None = None,
    timeout: int = 20,
) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read().decode("utf-8", errors="replace")
        if status in (401, 403):
            raise ValueError(f"Provider rejected the credential ({status}).") from exc
        raise ValueError(f"Provider returned HTTP {status}.") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not reach provider: {exc.reason}") from exc

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return status, data


def _bearer_get(url: str, token: str, *, extra_headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "MultiWorkAgent",
    }
    if extra_headers:
        headers.update(extra_headers)
    return _json_request(url, headers=headers)


def _github_user(token: str) -> IntegrationTestResult:
    try:
        status, user = _bearer_get(
            "https://api.github.com/user",
            token,
            extra_headers={"Accept": "application/vnd.github+json"},
        )
    except ValueError:
        status, user = _json_request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "MultiWorkAgent",
            },
        )
    login = user.get("login") or user.get("name") or "account"
    return IntegrationTestResult(
        ok=True,
        probe="github_user",
        message="GitHub accepted the credential.",
        detail=f"Signed in as {login}.",
        http_status=status,
    )


def _google_userinfo(token: str) -> IntegrationTestResult:
    status, user = _bearer_get("https://www.googleapis.com/oauth2/v3/userinfo", token)
    email = user.get("email") or user.get("name") or "google account"
    return IntegrationTestResult(
        ok=True,
        probe="google_userinfo",
        message="Google accepted the credential.",
        detail=f"Account: {email}.",
        http_status=status,
    )


def _slack_auth_test(token: str) -> IntegrationTestResult:
    status, data = _bearer_get("https://slack.com/api/auth.test", token)
    if not data.get("ok"):
        raise ValueError(data.get("error") or "Slack auth.test failed")
    team = data.get("team") or data.get("team_id") or "workspace"
    user = data.get("user") or ""
    detail = f"Workspace: {team}." + (f" User: {user}." if user else "")
    return IntegrationTestResult(
        ok=True,
        probe="slack_auth_test",
        message="Slack accepted the credential.",
        detail=detail,
        http_status=status,
    )


def _notion_me(token: str) -> IntegrationTestResult:
    status, user = _bearer_get(
        "https://api.notion.com/v1/users/me",
        token,
        extra_headers={"Notion-Version": "2022-06-28"},
    )
    name = user.get("name") or user.get("id") or "notion user"
    return IntegrationTestResult(
        ok=True,
        probe="notion_users_me",
        message="Notion accepted the credential.",
        detail=f"User: {name}.",
        http_status=status,
    )


def _linear_viewer(token: str) -> IntegrationTestResult:
    payload = json.dumps({"query": "{ viewer { id name email } }"}).encode("utf-8")
    status, data = _json_request(
        "https://api.linear.app/graphql",
        method="POST",
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "MultiWorkAgent",
        },
        body=payload,
    )
    if data.get("errors"):
        raise ValueError("Linear API returned an error for this token.")
    viewer = (data.get("data") or {}).get("viewer") or {}
    label = viewer.get("email") or viewer.get("name") or viewer.get("id") or "linear account"
    return IntegrationTestResult(
        ok=True,
        probe="linear_viewer",
        message="Linear accepted the credential.",
        detail=f"Viewer: {label}.",
        http_status=status,
    )


def _stripe_balance(token: str) -> IntegrationTestResult:
    status, _data = _json_request(
        "https://api.stripe.com/v1/balance",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "MultiWorkAgent",
        },
    )
    return IntegrationTestResult(
        ok=True,
        probe="stripe_balance",
        message="Stripe accepted the API key.",
        detail="Read-only balance endpoint responded successfully.",
        http_status=status,
    )


def _atlassian_resources(token: str) -> IntegrationTestResult:
    status, resources = _json_request(
        "https://api.atlassian.com/oauth/token/accessible-resources",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "MultiWorkAgent",
        },
    )
    if not isinstance(resources, list) or not resources:
        raise ValueError("No Atlassian sites are accessible with this token.")
    site = resources[0].get("name") or resources[0].get("id") or "site"
    return IntegrationTestResult(
        ok=True,
        probe="atlassian_accessible_resources",
        message="Atlassian accepted the credential.",
        detail=f"Accessible site: {site} ({len(resources)} total).",
        http_status=status,
    )


def _salesforce_identity(token: str, credentials: dict[str, Any]) -> IntegrationTestResult:
    instance = credentials.get("instance_url")
    if not isinstance(instance, str) or not instance.strip():
        raise ValueError("Salesforce connection is missing instance_url; reconnect via OAuth.")
    base = instance.rstrip("/")
    status, user = _bearer_get(f"{base}/services/oauth2/userinfo", token)
    label = user.get("email") or user.get("preferred_username") or user.get("user_id") or "user"
    return IntegrationTestResult(
        ok=True,
        probe="salesforce_userinfo",
        message="Salesforce accepted the credential.",
        detail=f"User: {label}.",
        http_status=status,
    )


def _airtable_whoami(token: str) -> IntegrationTestResult:
    status, data = _bearer_get("https://api.airtable.com/v0/meta/whoami", token)
    email = data.get("email") or data.get("id") or "airtable account"
    return IntegrationTestResult(
        ok=True,
        probe="airtable_whoami",
        message="Airtable accepted the credential.",
        detail=f"Account: {email}.",
        http_status=status,
    )


def _generic_bearer_get(
    *,
    probe: str,
    url: str,
    success_message: str,
    detail_from: Callable[[dict[str, Any]], str],
    token: str,
    extra_headers: dict[str, str] | None = None,
) -> IntegrationTestResult:
    status, data = _bearer_get(url, token, extra_headers=extra_headers)
    return IntegrationTestResult(
        ok=True,
        probe=probe,
        message=success_message,
        detail=detail_from(data),
        http_status=status,
    )


_PROBE_BY_SLUG: dict[str, Callable[[str, dict[str, Any]], IntegrationTestResult]] = {}


def _register(
    slug: str,
    fn: Callable[[str, dict[str, Any]], IntegrationTestResult],
) -> None:
    _PROBE_BY_SLUG[slug] = fn


_register("github", lambda t, _c: _github_user(t))
_register("gitlab", lambda t, _c: _generic_bearer_get(
    probe="gitlab_user",
    url="https://gitlab.com/api/v4/user",
    success_message="GitLab accepted the credential.",
    detail_from=lambda u: f"User: {u.get('username') or u.get('name') or 'account'}.",
    token=t,
))
_register("bitbucket", lambda t, _c: _generic_bearer_get(
    probe="bitbucket_user",
    url="https://api.bitbucket.org/2.0/user",
    success_message="Bitbucket accepted the credential.",
    detail_from=lambda u: f"User: {u.get('username') or u.get('display_name') or 'account'}.",
    token=t,
))
_register("netlify", lambda t, _c: _generic_bearer_get(
    probe="netlify_user",
    url="https://api.netlify.com/api/v1/user",
    success_message="Netlify accepted the credential.",
    detail_from=lambda u: f"Account: {u.get('email') or u.get('full_name') or 'netlify'}.",
    token=t,
))
_register("vercel", lambda t, _c: _generic_bearer_get(
    probe="vercel_user",
    url="https://api.vercel.com/v2/user",
    success_message="Vercel accepted the credential.",
    detail_from=lambda u: f"User: {u.get('username') or u.get('email') or 'vercel'}.",
    token=t,
))
_register("slack", lambda t, _c: _slack_auth_test(t))
_register(
    "google-workspace-gmail-docs-drive-sheets-calendar",
    lambda t, _c: _google_userinfo(t),
)
_register("google-cloud-platform-gcp", lambda t, _c: _google_userinfo(t))
_register("google-bigquery", lambda t, _c: _google_userinfo(t))
_register("google-cloud-storage", lambda t, _c: _google_userinfo(t))
_register("google-meet", lambda t, _c: _google_userinfo(t))
_register("microsoft-365-outlook-onedrive-sharepoint-excel", lambda t, _c: _generic_bearer_get(
    probe="microsoft_graph_me",
    url="https://graph.microsoft.com/v1.0/me",
    success_message="Microsoft 365 accepted the credential.",
    detail_from=lambda u: f"User: {u.get('userPrincipalName') or u.get('displayName') or 'account'}.",
    token=t,
))
_register("microsoft-teams", lambda t, _c: _PROBE_BY_SLUG["microsoft-365-outlook-onedrive-sharepoint-excel"](t, _c))
_register("microsoft-azure", lambda t, _c: _PROBE_BY_SLUG["microsoft-365-outlook-onedrive-sharepoint-excel"](t, _c))
_register("dynamics-365", lambda t, _c: _PROBE_BY_SLUG["microsoft-365-outlook-onedrive-sharepoint-excel"](t, _c))
_register("jira", lambda t, _c: _atlassian_resources(t))
_register("confluence", lambda t, _c: _atlassian_resources(t))
_register("notion", lambda t, _c: _notion_me(t))
_register("linear", lambda t, _c: _linear_viewer(t))
_register("asana", lambda t, _c: _generic_bearer_get(
    probe="asana_me",
    url="https://app.asana.com/api/1.0/users/me",
    success_message="Asana accepted the credential.",
    detail_from=lambda u: f"User: {(u.get('data') or {}).get('email') or 'asana account'}.",
    token=t,
))
_register("discord", lambda t, _c: _generic_bearer_get(
    probe="discord_me",
    url="https://discord.com/api/users/@me",
    success_message="Discord accepted the credential.",
    detail_from=lambda u: f"User: {u.get('username') or u.get('id') or 'discord'}.",
    token=t,
))
_register("hubspot", lambda t, _c: _generic_bearer_get(
    probe="hubspot_contacts",
    url="https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
    success_message="HubSpot accepted the credential.",
    detail_from=lambda _: "CRM API responded successfully.",
    token=t,
))
_register("salesforce", lambda t, c: _salesforce_identity(t, c))
_register("stripe", lambda t, _c: _stripe_balance(t))
_register("airtable", lambda t, _c: _airtable_whoami(t))
_register("zoom", lambda t, _c: _generic_bearer_get(
    probe="zoom_me",
    url="https://api.zoom.us/v2/users/me",
    success_message="Zoom accepted the credential.",
    detail_from=lambda u: f"User: {u.get('email') or u.get('id') or 'zoom'}.",
    token=t,
))
def _clickup_user(token: str) -> IntegrationTestResult:
    status, data = _json_request(
        "https://api.clickup.com/api/v2/user",
        headers={
            "Authorization": token,
            "Accept": "application/json",
            "User-Agent": "MultiWorkAgent",
        },
    )
    user = data.get("user") if isinstance(data.get("user"), dict) else data
    label = (
        (user or {}).get("email")
        or (user or {}).get("username")
        or (user or {}).get("id")
        or "clickup account"
    )
    return IntegrationTestResult(
        ok=True,
        probe="clickup_user",
        message="ClickUp accepted the credential.",
        detail=f"User: {label}.",
        http_status=status,
    )


_register("xero", lambda t, _c: _generic_bearer_get(
    probe="xero_organisations",
    url="https://api.xero.com/api.xro/2.0/Organisation",
    success_message="Xero accepted the credential.",
    detail_from=lambda _: "Organisation API responded successfully.",
    token=t,
    extra_headers={"Accept": "application/json"},
))
_register("clickup", lambda t, _c: _clickup_user(t))


def test_integration_connection(
    *,
    provider_slug: str,
    auth_type: str,
    status: str,
    credentials: dict[str, Any] | None,
) -> IntegrationTestResult:
    if status != "connected":
        return IntegrationTestResult(
            ok=False,
            probe="connection_status",
            message="This integration is not connected.",
            detail="Finish OAuth or save an API key, then test again.",
        )
    if not credentials:
        return IntegrationTestResult(
            ok=False,
            probe="credentials",
            message="Stored credentials could not be read.",
            detail="Try disconnecting and connecting again.",
        )
    token = _token(credentials)
    if not token:
        return IntegrationTestResult(
            ok=False,
            probe="credentials",
            message="No access token or API key found for this connection.",
        )

    probe_fn = _PROBE_BY_SLUG.get(provider_slug)
    if not probe_fn:
        return IntegrationTestResult(
            ok=False,
            probe="unsupported",
            message="No automated API test is configured for this provider yet.",
            detail=(
                "Your credential is stored. We will add a read-only health check for this "
                "integration in a future update."
            ),
        )

    try:
        return probe_fn(token, credentials)
    except ValueError as exc:
        return IntegrationTestResult(
            ok=False,
            probe=f"{provider_slug}_probe",
            message=str(exc),
        )
