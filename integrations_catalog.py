"""
Canonical integration catalog for MultiWorkAgent.

Each business connects its own credentials (OAuth or API key). The agent acts
through those connections with scoped read/write access — never shared across
businesses. Product subscription billing for this app uses Square; integrations
below are third-party systems the agent can operate on behalf of a business.
"""

from __future__ import annotations

from typing import Any, TypedDict

import integration_oauth
from integration_oauth_registry import OAUTH_PROVIDERS


class Integration(TypedDict):
    slug: str
    name: str


class IntegrationWithAuth(Integration, total=False):
    auth_methods: list[str]
    oauth_available: bool
    oauth_configured: bool
    oauth_offered: bool


class IntegrationCategory(TypedDict):
    id: str
    label: str
    integrations: list[Integration]


def _slug(name: str) -> str:
    return (
        name.lower()
        .replace(" ", "-")
        .replace("(", "")
        .replace(")", "")
        .replace(".", "")
        .replace(",", "")
        .replace("'", "")
        .replace("/", "-")
        .replace("--", "-")
    )


def _items(names: list[str]) -> list[Integration]:
    return [{"slug": _slug(n), "name": n} for n in names]


INTEGRATION_CATEGORIES: list[IntegrationCategory] = [
    {
        "id": "vcs_cicd",
        "label": "Version Control, CI/CD & Developer Tools",
        "integrations": _items([
            "GitHub",
            "GitLab",
            "Bitbucket",
            "Vercel",
            "Netlify",
            "Render",
            "AWS",
            "Google Cloud Platform (GCP)",
            "Microsoft Azure",
            "Docker Registry",
            "Kubernetes Registry",
            "Sentry",
            "Datadog",
            "Cloudflare",
            "Postman",
            "CircleCI",
            "Travis CI",
        ]),
    },
    {
        "id": "cms",
        "label": "CMS, Web Builders & Content Platforms",
        "integrations": _items([
            "WordPress",
            "Webflow",
            "Wix",
            "Squarespace",
            "Ghost",
            "Strapi",
            "Contentful",
            "Sanity",
        ]),
    },
    {
        "id": "crm",
        "label": "CRM, Sales & Revenue Operations",
        "integrations": _items([
            "Salesforce",
            "HubSpot",
            "Zoho CRM",
            "Pipedrive",
            "HighLevel (GoHighLevel)",
            "ActiveCampaign",
            "Keap (Infusionsoft)",
            "Dynamics 365",
            "Gong",
            "Chorus",
        ]),
    },
    {
        "id": "support",
        "label": "Customer Support & Ticketing",
        "integrations": _items([
            "Zendesk",
            "Intercom",
            "Freshdesk",
            "Help Scout",
            "ServiceNow",
            "Gorgias",
            "Front",
        ]),
    },
    {
        "id": "data",
        "label": "Databases, Storage & Vector Search",
        "integrations": _items([
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Redis",
            "Supabase",
            "Firebase",
            "Snowflake",
            "Google BigQuery",
            "Amazon Redshift",
            "Elasticsearch",
            "Pinecone",
            "Weaviate",
            "Qdrant",
            "ChromaDB",
            "Milvus",
            "Neo4j",
            "Amazon S3",
            "Google Cloud Storage",
        ]),
    },
    {
        "id": "comms",
        "label": "Team Communication & Messaging",
        "integrations": _items([
            "Slack",
            "Microsoft Teams",
            "Discord",
            "Telegram",
            "WhatsApp Business API",
            "Twilio",
            "SendGrid",
            "Postmark",
            "Mailchimp",
        ]),
    },
    {
        "id": "pm",
        "label": "Project Management & Productivity",
        "integrations": _items([
            "Jira",
            "Asana",
            "Trello",
            "Linear",
            "ClickUp",
            "Monday.com",
            "Basecamp",
            "Notion",
            "Confluence",
            "Coda",
        ]),
    },
    {
        "id": "automation",
        "label": "Workflow Automation & Middleware",
        "integrations": _items([
            "Zapier",
            "Make (Integromat)",
            "n8n",
            "Pipedream",
        ]),
    },
    {
        "id": "commerce",
        "label": "E-Commerce & Retail",
        "integrations": _items([
            "Shopify",
            "WooCommerce",
            "BigCommerce",
            "Magento (Adobe Commerce)",
            "Amazon Seller Central",
            "eBay API",
            "Etsy API",
            "Square",
        ]),
    },
    {
        "id": "finance",
        "label": "Financials, Billing & ERP",
        "integrations": _items([
            "Stripe",
            "PayPal",
            "Brex",
            "QuickBooks Online",
            "Xero",
            "Netsuite",
            "SAP",
            "Bill.com",
            "Chargebee",
            "Recurly",
        ]),
    },
    {
        "id": "workspace",
        "label": "Workspace & Productivity Suites",
        "integrations": _items([
            "Google Workspace (Gmail, Docs, Drive, Sheets, Calendar)",
            "Microsoft 365 (Outlook, OneDrive, SharePoint, Excel)",
            "Airtable",
            "Calendly",
            "DocuSign",
            "PandaDoc",
            "Zoom",
            "Google Meet",
        ]),
    },
]


def integration_count() -> int:
    return sum(len(c["integrations"]) for c in INTEGRATION_CATEGORIES)


def flat_integration_names() -> list[str]:
    names: list[str] = []
    for category in INTEGRATION_CATEGORIES:
        names.extend(i["name"] for i in category["integrations"])
    return names


def get_integration(slug: str) -> Integration | None:
    for category in INTEGRATION_CATEGORIES:
        for item in category["integrations"]:
            if item["slug"] == slug:
                return item
    return None


def enrich_integration(item: Integration) -> IntegrationWithAuth:
    slug = item["slug"]
    oauth_available = integration_oauth.is_oauth_provider(slug)
    oauth_configured = (
        integration_oauth.is_provider_configured(slug) if oauth_available else False
    )
    oauth_offered = oauth_available and oauth_configured
    auth_methods = ["api_key"]
    if oauth_offered:
        auth_methods.append("oauth")
    return {
        **item,
        "auth_methods": auth_methods,
        "oauth_available": oauth_available,
        "oauth_configured": oauth_configured,
        "oauth_offered": oauth_offered,
    }


def categories_with_auth() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for category in INTEGRATION_CATEGORIES:
        out.append(
            {
                **category,
                "integrations": [enrich_integration(item) for item in category["integrations"]],
            }
        )
    return out


def catalog_for_api() -> dict[str, Any]:
    oauth_ready = sum(
        1
        for category in INTEGRATION_CATEGORIES
        for item in category["integrations"]
        if integration_oauth.is_oauth_provider(item["slug"])
    )
    oauth_configured = sum(
        1
        for category in INTEGRATION_CATEGORIES
        for item in category["integrations"]
        if integration_oauth.is_provider_configured(item["slug"])
    )
    oauth_urls_wired = sum(1 for p in OAUTH_PROVIDERS.values() if p.urls_configured)
    return {
        "total": integration_count(),
        "categories": categories_with_auth(),
        "oauth": {
            "definitions": oauth_ready,
            "configured_on_server": oauth_configured,
            "urls_wired": oauth_urls_wired,
        },
        "agent_policy": {
            "summary": (
                "The agent uses per-business connections to read and mutate data "
                "where OAuth/API scopes allow. Destructive actions require confirmation."
            ),
            "scopes": ["read", "write", "automate"],
        },
    }
