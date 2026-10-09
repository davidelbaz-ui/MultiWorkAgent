"""Allowed HTTPS API origins per integration slug (SSRF guard for agent HTTP tools)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

# Prefixes must be https:// and include trailing slash where path-scoped.
INTEGRATION_API_PREFIXES: dict[str, list[str]] = {
    "github": ["https://api.github.com/"],
    "gitlab": ["https://gitlab.com/api/v4/", "https://gitlab.com/api/"],
    "bitbucket": ["https://api.bitbucket.org/"],
    "netlify": ["https://api.netlify.com/"],
    "vercel": ["https://api.vercel.com/"],
    "slack": ["https://slack.com/api/"],
    "notion": ["https://api.notion.com/"],
    "linear": ["https://api.linear.app/"],
    "asana": ["https://app.asana.com/api/"],
    "discord": ["https://discord.com/api/"],
    "hubspot": ["https://api.hubapi.com/"],
    "stripe": ["https://api.stripe.com/"],
    "airtable": ["https://api.airtable.com/"],
    "zoom": ["https://api.zoom.us/"],
    "xero": ["https://api.xero.com/"],
    "clickup": ["https://api.clickup.com/"],
    "jira": ["https://api.atlassian.com/"],
    "confluence": ["https://api.atlassian.com/"],
    "google-workspace-gmail-docs-drive-sheets-calendar": [
        "https://www.googleapis.com/",
        "https://gmail.googleapis.com/",
        "https://drive.googleapis.com/",
        "https://sheets.googleapis.com/",
        "https://docs.googleapis.com/",
        "https://calendar.googleapis.com/",
    ],
    "google-cloud-platform-gcp": ["https://www.googleapis.com/"],
    "google-bigquery": ["https://bigquery.googleapis.com/", "https://www.googleapis.com/"],
    "google-cloud-storage": ["https://storage.googleapis.com/", "https://www.googleapis.com/"],
    "google-meet": ["https://meet.googleapis.com/", "https://www.googleapis.com/"],
    "microsoft-365-outlook-onedrive-sharepoint-excel": ["https://graph.microsoft.com/"],
    "microsoft-teams": ["https://graph.microsoft.com/"],
    "microsoft-azure": ["https://management.azure.com/", "https://graph.microsoft.com/"],
    "dynamics-365": ["https://graph.microsoft.com/"],
}

_GOOGLE_SLUG_PREFIX = INTEGRATION_API_PREFIXES["google-workspace-gmail-docs-drive-sheets-calendar"]
_MICROSOFT_SLUG_PREFIX = INTEGRATION_API_PREFIXES["microsoft-365-outlook-onedrive-sharepoint-excel"]


def _credential_url_prefixes(credentials: dict[str, Any]) -> list[str]:
    prefixes: list[str] = []
    for key in ("api_base_url", "base_url", "site_url", "instance_url", "rest_url"):
        value = credentials.get(key)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned.startswith("https://"):
            continue
        base = cleaned.rstrip("/") + "/"
        prefixes.append(base)
        if key == "site_url" and "/wp-json" not in base.lower():
            prefixes.append(base.rstrip("/") + "/wp-json/")
    return prefixes


def allowed_prefixes_for(provider_slug: str, credentials: dict[str, Any] | None) -> list[str]:
    slug = provider_slug.strip().lower()
    prefixes: list[str] = []
    if slug in INTEGRATION_API_PREFIXES:
        prefixes.extend(INTEGRATION_API_PREFIXES[slug])
    elif slug.startswith("google-"):
        prefixes.extend(_GOOGLE_SLUG_PREFIX)
    elif slug in ("microsoft-teams", "microsoft-azure", "dynamics-365"):
        prefixes.extend(_MICROSOFT_SLUG_PREFIX)
    if credentials:
        prefixes.extend(_credential_url_prefixes(credentials))
    # Salesforce instance_url is required and stored on OAuth.
    if slug == "salesforce" and credentials:
        instance = credentials.get("instance_url")
        if isinstance(instance, str) and instance.strip().startswith("https://"):
            prefixes.append(instance.rstrip("/") + "/")
    seen: set[str] = set()
    out: list[str] = []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _host_is_public(hostname: str) -> bool:
    host = hostname.strip().lower().rstrip(".")
    if not host or host == "localhost":
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        addr = ipaddress.ip_address(host)
        return not (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        )
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            return False
        for info in infos:
            sockaddr = info[4]
            if not sockaddr:
                continue
            ip = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if (
                addr.is_private
                or addr.is_loopback
                or addr.is_link_local
                or addr.is_reserved
                or addr.is_multicast
            ):
                return False
        return True


def resolve_integration_url(
    *,
    provider_slug: str,
    path_or_url: str,
    credentials: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """
    Return (absolute_https_url, error_message).
    path_or_url may be absolute https URL or path starting with / relative to first allowed prefix.
    """
    raw = (path_or_url or "").strip()
    if not raw:
        return None, "path_or_url is required."

    prefixes = allowed_prefixes_for(provider_slug, credentials)
    if not prefixes:
        return None, (
            f"No API base URL is configured for integration '{provider_slug}'. "
            "Connect OAuth for this provider, or store api_base_url/site_url in credentials "
            "(for example https://yoursite.com/wp-json/wp/v2 for WordPress)."
        )

    if raw.startswith("https://"):
        url = raw
    elif raw.startswith("http://"):
        return None, "Only https:// URLs are allowed."
    elif raw.startswith("/"):
        url = prefixes[0].rstrip("/") + raw
    else:
        url = prefixes[0].rstrip("/") + "/" + raw.lstrip("/")

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return None, "URL must be https with a valid host."

    if not _host_is_public(parsed.hostname or ""):
        return None, "Requests to private or local networks are not allowed."

    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"
    if parsed.query:
        normalized += f"?{parsed.query}"

    path_with_slash = normalized if normalized.endswith("/") else normalized + "/"
    allowed = False
    for prefix in prefixes:
        if normalized.startswith(prefix) or path_with_slash.startswith(prefix):
            allowed = True
            break
    if not allowed:
        return None, (
            "URL is not under an allowed API base for this integration. "
            f"Allowed bases: {', '.join(prefixes[:5])}"
            + (" …" if len(prefixes) > 5 else "")
        )
    return normalized, None
