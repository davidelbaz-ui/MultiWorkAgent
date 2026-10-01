"""
OAuth 2.0 provider definitions — one entry per catalog integration (109 total).

Set the env vars listed on each provider in server `.env` (see `.env.example`).
Fill in authorize/token URLs in `_WIRED_OAUTH` when wiring OAuth for that vendor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from integration_oauth_catalog_data import CATALOG_INTEGRATIONS

TokenAuthStyle = Literal["body", "basic", "json"]

# Shared or short env names (default is {SLUG_UPPER}_OAUTH_CLIENT_ID).
ENV_KEY_OVERRIDES: dict[str, tuple[str, str]] = {
    "github": ("GITHUB_OAUTH_CLIENT_ID", "GITHUB_OAUTH_CLIENT_SECRET"),
    "gitlab": ("GITLAB_OAUTH_CLIENT_ID", "GITLAB_OAUTH_CLIENT_SECRET"),
    "bitbucket": ("BITBUCKET_OAUTH_CLIENT_ID", "BITBUCKET_OAUTH_CLIENT_SECRET"),
    "google-workspace-gmail-docs-drive-sheets-calendar": (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
    ),
    "google-cloud-platform-gcp": ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
    "google-bigquery": ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
    "google-cloud-storage": ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
    "google-meet": ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"),
    "microsoft-365-outlook-onedrive-sharepoint-excel": (
        "MICROSOFT_OAUTH_CLIENT_ID",
        "MICROSOFT_OAUTH_CLIENT_SECRET",
    ),
    "microsoft-teams": ("MICROSOFT_OAUTH_CLIENT_ID", "MICROSOFT_OAUTH_CLIENT_SECRET"),
    "microsoft-azure": ("MICROSOFT_OAUTH_CLIENT_ID", "MICROSOFT_OAUTH_CLIENT_SECRET"),
    "dynamics-365": ("MICROSOFT_OAUTH_CLIENT_ID", "MICROSOFT_OAUTH_CLIENT_SECRET"),
    "jira": ("ATLASSIAN_OAUTH_CLIENT_ID", "ATLASSIAN_OAUTH_CLIENT_SECRET"),
    "confluence": ("ATLASSIAN_OAUTH_CLIENT_ID", "ATLASSIAN_OAUTH_CLIENT_SECRET"),
    "slack": ("SLACK_OAUTH_CLIENT_ID", "SLACK_OAUTH_CLIENT_SECRET"),
    "notion": ("NOTION_OAUTH_CLIENT_ID", "NOTION_OAUTH_CLIENT_SECRET"),
    "linear": ("LINEAR_OAUTH_CLIENT_ID", "LINEAR_OAUTH_CLIENT_SECRET"),
    "asana": ("ASANA_OAUTH_CLIENT_ID", "ASANA_OAUTH_CLIENT_SECRET"),
    "discord": ("DISCORD_OAUTH_CLIENT_ID", "DISCORD_OAUTH_CLIENT_SECRET"),
    "salesforce": ("SALESFORCE_OAUTH_CLIENT_ID", "SALESFORCE_OAUTH_CLIENT_SECRET"),
    "hubspot": ("HUBSPOT_OAUTH_CLIENT_ID", "HUBSPOT_OAUTH_CLIENT_SECRET"),
    "stripe": ("STRIPE_OAUTH_CLIENT_ID", "STRIPE_OAUTH_CLIENT_SECRET"),
    "quickbooks-online": ("QUICKBOOKS_OAUTH_CLIENT_ID", "QUICKBOOKS_OAUTH_CLIENT_SECRET"),
    "xero": ("XERO_OAUTH_CLIENT_ID", "XERO_OAUTH_CLIENT_SECRET"),
    "zoom": ("ZOOM_OAUTH_CLIENT_ID", "ZOOM_OAUTH_CLIENT_SECRET"),
    "airtable": ("AIRTABLE_OAUTH_CLIENT_ID", "AIRTABLE_OAUTH_CLIENT_SECRET"),
}


@dataclass(frozen=True)
class OAuthProviderTemplate:
    slug: str
    display_name: str
    authorize_url: str
    token_url: str
    scopes: str
    client_id_env: str
    client_secret_env: str
    authorize_extra: dict[str, str] = field(default_factory=dict)
    token_auth: TokenAuthStyle = "body"
    accept_json_token: bool = True
    urls_configured: bool = True


def _env_keys_for_slug(slug: str) -> tuple[str, str]:
    if slug in ENV_KEY_OVERRIDES:
        return ENV_KEY_OVERRIDES[slug]
    prefix = slug.upper().replace("-", "_")
    return f"{prefix}_OAUTH_CLIENT_ID", f"{prefix}_OAUTH_CLIENT_SECRET"


def _register(items: list[OAuthProviderTemplate]) -> dict[str, OAuthProviderTemplate]:
    out: dict[str, OAuthProviderTemplate] = {}
    for item in items:
        if item.slug in out:
            raise ValueError(f"duplicate OAuth slug: {item.slug}")
        out[item.slug] = item
    return out


# OAuth authorize/token URLs filled in for these slugs (add more as you go).
_WIRED_OAUTH: list[OAuthProviderTemplate] = [
    OAuthProviderTemplate(
        slug="github",
        display_name="GitHub",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scopes="read:user repo",
        client_id_env="GITHUB_OAUTH_CLIENT_ID",
        client_secret_env="GITHUB_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="gitlab",
        display_name="GitLab",
        authorize_url="https://gitlab.com/oauth/authorize",
        token_url="https://gitlab.com/oauth/token",
        scopes="read_user api read_api",
        client_id_env="GITLAB_OAUTH_CLIENT_ID",
        client_secret_env="GITLAB_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="bitbucket",
        display_name="Bitbucket",
        authorize_url="https://bitbucket.org/site/oauth2/authorize",
        token_url="https://bitbucket.org/site/oauth2/access_token",
        scopes="repository account",
        client_id_env="BITBUCKET_OAUTH_CLIENT_ID",
        client_secret_env="BITBUCKET_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="google-workspace-gmail-docs-drive-sheets-calendar",
        display_name="Google Workspace (Gmail, Docs, Drive, Sheets, Calendar)",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=(
            "openid email profile "
            "https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/drive.readonly "
            "https://www.googleapis.com/auth/spreadsheets.readonly "
            "https://www.googleapis.com/auth/calendar.readonly"
        ),
        client_id_env="GOOGLE_OAUTH_CLIENT_ID",
        client_secret_env="GOOGLE_OAUTH_CLIENT_SECRET",
        authorize_extra={"access_type": "offline", "prompt": "consent"},
    ),
    OAuthProviderTemplate(
        slug="microsoft-365-outlook-onedrive-sharepoint-excel",
        display_name="Microsoft 365 (Outlook, OneDrive, SharePoint, Excel)",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scopes="openid offline_access User.Read Files.Read.All Sites.Read.All",
        client_id_env="MICROSOFT_OAUTH_CLIENT_ID",
        client_secret_env="MICROSOFT_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="slack",
        display_name="Slack",
        authorize_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        scopes="channels:read chat:write users:read",
        client_id_env="SLACK_OAUTH_CLIENT_ID",
        client_secret_env="SLACK_OAUTH_CLIENT_SECRET",
    ),
        OAuthProviderTemplate(
            slug="jira",
            display_name="Jira",
            authorize_url="https://auth.atlassian.com/authorize",
            token_url="https://auth.atlassian.com/oauth/token",
            scopes="read:jira-work write:jira-work read:jira-user offline_access",
            client_id_env="ATLASSIAN_OAUTH_CLIENT_ID",
            client_secret_env="ATLASSIAN_OAUTH_CLIENT_SECRET",
            authorize_extra={"audience": "api.atlassian.com", "prompt": "consent"},
            token_auth="json",
        ),
        OAuthProviderTemplate(
            slug="confluence",
            display_name="Confluence",
            authorize_url="https://auth.atlassian.com/authorize",
            token_url="https://auth.atlassian.com/oauth/token",
            scopes="read:confluence-content.all write:confluence-content offline_access",
            client_id_env="ATLASSIAN_OAUTH_CLIENT_ID",
            client_secret_env="ATLASSIAN_OAUTH_CLIENT_SECRET",
            authorize_extra={"audience": "api.atlassian.com", "prompt": "consent"},
            token_auth="json",
        ),
    OAuthProviderTemplate(
        slug="notion",
        display_name="Notion",
        authorize_url="https://api.notion.com/v1/oauth/authorize",
        token_url="https://api.notion.com/v1/oauth/token",
        scopes="",
        client_id_env="NOTION_OAUTH_CLIENT_ID",
        client_secret_env="NOTION_OAUTH_CLIENT_SECRET",
        token_auth="basic",
    ),
    OAuthProviderTemplate(
        slug="linear",
        display_name="Linear",
        authorize_url="https://linear.app/oauth/authorize",
        token_url="https://api.linear.app/oauth/token",
        scopes="read write",
        client_id_env="LINEAR_OAUTH_CLIENT_ID",
        client_secret_env="LINEAR_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="asana",
        display_name="Asana",
        authorize_url="https://app.asana.com/-/oauth_authorize",
        token_url="https://app.asana.com/-/oauth_token",
        scopes="default",
        client_id_env="ASANA_OAUTH_CLIENT_ID",
        client_secret_env="ASANA_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="discord",
        display_name="Discord",
        authorize_url="https://discord.com/api/oauth2/authorize",
        token_url="https://discord.com/api/oauth2/token",
        scopes="identify guilds bot",
        client_id_env="DISCORD_OAUTH_CLIENT_ID",
        client_secret_env="DISCORD_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="salesforce",
        display_name="Salesforce",
        authorize_url="https://login.salesforce.com/services/oauth2/authorize",
        token_url="https://login.salesforce.com/services/oauth2/token",
        scopes="api refresh_token",
        client_id_env="SALESFORCE_OAUTH_CLIENT_ID",
        client_secret_env="SALESFORCE_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="hubspot",
        display_name="HubSpot",
        authorize_url="https://app.hubspot.com/oauth/authorize",
        token_url="https://api.hubapi.com/oauth/v1/token",
        scopes="crm.objects.contacts.read crm.objects.deals.read",
        client_id_env="HUBSPOT_OAUTH_CLIENT_ID",
        client_secret_env="HUBSPOT_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="stripe",
        display_name="Stripe",
        authorize_url="https://connect.stripe.com/oauth/authorize",
        token_url="https://connect.stripe.com/oauth/token",
        scopes="read_write",
        client_id_env="STRIPE_OAUTH_CLIENT_ID",
        client_secret_env="STRIPE_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="quickbooks-online",
        display_name="QuickBooks Online",
        authorize_url="https://appcenter.intuit.com/connect/oauth2",
        token_url="https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer",
        scopes="com.intuit.quickbooks.accounting",
        client_id_env="QUICKBOOKS_OAUTH_CLIENT_ID",
        client_secret_env="QUICKBOOKS_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="xero",
        display_name="Xero",
        authorize_url="https://login.xero.com/identity/connect/authorize",
        token_url="https://identity.xero.com/connect/token",
        scopes="openid profile email accounting.transactions accounting.settings offline_access",
        client_id_env="XERO_OAUTH_CLIENT_ID",
        client_secret_env="XERO_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="zoom",
        display_name="Zoom",
        authorize_url="https://zoom.us/oauth/authorize",
        token_url="https://zoom.us/oauth/token",
        scopes="user:read meeting:read",
        client_id_env="ZOOM_OAUTH_CLIENT_ID",
        client_secret_env="ZOOM_OAUTH_CLIENT_SECRET",
    ),
    OAuthProviderTemplate(
        slug="airtable",
        display_name="Airtable",
        authorize_url="https://airtable.com/oauth2/v1/authorize",
        token_url="https://airtable.com/oauth2/v1/token",
        scopes="data.records:read data.records:write schema.bases:read",
        client_id_env="AIRTABLE_OAUTH_CLIENT_ID",
        client_secret_env="AIRTABLE_OAUTH_CLIENT_SECRET",
    ),
]

_WIRED_BY_SLUG: dict[str, OAuthProviderTemplate] = {p.slug: p for p in _WIRED_OAUTH}


def _build_all_providers() -> list[OAuthProviderTemplate]:
    if len(CATALOG_INTEGRATIONS) != 109:
        raise ValueError(f"expected 109 catalog integrations, got {len(CATALOG_INTEGRATIONS)}")
    items: list[OAuthProviderTemplate] = []
    for slug, name in CATALOG_INTEGRATIONS:
        if slug in _WIRED_BY_SLUG:
            items.append(_WIRED_BY_SLUG[slug])
            continue
        client_id_env, client_secret_env = _env_keys_for_slug(slug)
        items.append(
            OAuthProviderTemplate(
                slug=slug,
                display_name=name,
                authorize_url="",
                token_url="",
                scopes="",
                client_id_env=client_id_env,
                client_secret_env=client_secret_env,
                urls_configured=False,
            )
        )
    return items


OAUTH_PROVIDERS: dict[str, OAuthProviderTemplate] = _register(_build_all_providers())


def oauth_provider_count() -> int:
    return len(OAUTH_PROVIDERS)


def list_env_keys_table() -> list[dict[str, str]]:
    """All 109 integrations with env var names (for operators)."""
    rows: list[dict[str, str]] = []
    for slug, name in CATALOG_INTEGRATIONS:
        provider = OAUTH_PROVIDERS[slug]
        rows.append(
            {
                "slug": slug,
                "name": name,
                "client_id_env": provider.client_id_env,
                "client_secret_env": provider.client_secret_env,
                "urls_configured": "yes" if provider.urls_configured else "no",
            }
        )
    return rows


def env_vars_for_deploy_docs() -> list[dict[str, Any]]:
    """Unique env var pairs for operator setup docs."""
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, Any]] = []
    for provider in OAUTH_PROVIDERS.values():
        key = (provider.client_id_env, provider.client_secret_env)
        if key in seen:
            continue
        seen.add(key)
        slugs = [p.slug for p in OAUTH_PROVIDERS.values() if p.client_id_env == key[0]]
        rows.append(
            {
                "client_id_env": key[0],
                "client_secret_env": key[1],
                "provider_slugs": slugs,
            }
        )
    return rows
