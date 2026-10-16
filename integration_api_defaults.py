"""Default HTTPS API bases per integration catalog slug (agent HTTP + connection probes)."""

from __future__ import annotations

from integration_oauth_catalog_data import CATALOG_INTEGRATIONS

# Prefixes must be https:// with trailing slash where path-scoped.
INTEGRATION_DEFAULT_API_PREFIXES: dict[str, list[str]] = {
    "github": ["https://api.github.com/"],
    "gitlab": ["https://gitlab.com/api/v4/"],
    "bitbucket": ["https://api.bitbucket.org/2.0/"],
    "vercel": ["https://api.vercel.com/"],
    "netlify": ["https://api.netlify.com/api/v1/"],
    "render": ["https://api.render.com/v1/"],
    "aws": ["https://sts.amazonaws.com/"],
    "google-cloud-platform-gcp": ["https://www.googleapis.com/"],
    "microsoft-azure": ["https://management.azure.com/"],
    "docker-registry": ["https://hub.docker.com/v2/"],
    "kubernetes-registry": [],
    "sentry": ["https://sentry.io/api/0/"],
    "datadog": ["https://api.datadoghq.com/api/v1/"],
    "cloudflare": ["https://api.cloudflare.com/client/v4/"],
    "postman": ["https://api.getpostman.com/"],
    "circleci": ["https://circleci.com/api/v2/"],
    "travis-ci": ["https://api.travis-ci.com/"],
    "wordpress": [],
    "webflow": ["https://api.webflow.com/v2/"],
    "wix": ["https://www.wixapis.com/"],
    "squarespace": ["https://api.squarespace.com/1.0/"],
    "ghost": ["https://ghost.org/ghost/api/admin/"],
    "strapi": [],
    "contentful": ["https://api.contentful.com/"],
    "sanity": ["https://api.sanity.io/"],
    "salesforce": [],
    "hubspot": ["https://api.hubapi.com/"],
    "zoho-crm": ["https://www.zohoapis.com/crm/v6/"],
    "pipedrive": ["https://api.pipedrive.com/v1/"],
    "highlevel-gohighlevel": ["https://services.leadconnectorhq.com/"],
    "activecampaign": ["https://api.activecampaign.com/api/3/"],
    "keap-infusionsoft": ["https://api.infusionsoft.com/crm/rest/v1/"],
    "dynamics-365": ["https://graph.microsoft.com/v1.0/"],
    "gong": ["https://api.gong.io/v2/"],
    "chorus": ["https://chorus.ai/v3/"],
    "zendesk": [],
    "intercom": ["https://api.intercom.io/"],
    "freshdesk": [],
    "help-scout": ["https://api.helpscout.net/v2/"],
    "servicenow": [],
    "gorgias": ["https://api.gorgias.com/api/"],
    "front": ["https://api2.frontapp.com/"],
    "supabase": ["https://api.supabase.com/v1/"],
    "firebase": ["https://firebase.googleapis.com/"],
    "snowflake": [],
    "google-bigquery": ["https://bigquery.googleapis.com/"],
    "amazon-redshift": [],
    "elasticsearch": [],
    "pinecone": ["https://api.pinecone.io/"],
    "weaviate": [],
    "qdrant": [],
    "chromadb": [],
    "milvus": [],
    "neo4j": [],
    "amazon-s3": ["https://s3.amazonaws.com/"],
    "google-cloud-storage": ["https://storage.googleapis.com/"],
    "slack": ["https://slack.com/api/"],
    "microsoft-teams": ["https://graph.microsoft.com/v1.0/"],
    "discord": ["https://discord.com/api/v10/"],
    "telegram": ["https://api.telegram.org/"],
    "whatsapp-business-api": ["https://graph.facebook.com/v21.0/"],
    "twilio": ["https://api.twilio.com/2010-04-01/"],
    "sendgrid": ["https://api.sendgrid.com/v3/"],
    "postmark": ["https://api.postmarkapp.com/"],
    "mailchimp": [],
    "jira": ["https://api.atlassian.com/"],
    "asana": ["https://app.asana.com/api/1.0/"],
    "trello": ["https://api.trello.com/1/"],
    "linear": ["https://api.linear.app/"],
    "clickup": ["https://api.clickup.com/api/v2/"],
    "mondaycom": ["https://api.monday.com/v2/"],
    "basecamp": ["https://3.basecampapi.com/"],
    "notion": ["https://api.notion.com/v1/"],
    "confluence": ["https://api.atlassian.com/"],
    "coda": ["https://coda.io/apis/v1/"],
    "zapier": ["https://api.zapier.com/v1/"],
    "make-integromat": ["https://api.integromat.com/v1/"],
    "n8n": [],
    "pipedream": ["https://api.pipedream.com/v1/"],
    "shopify": [],
    "woocommerce": [],
    "bigcommerce": ["https://api.bigcommerce.com/stores/"],
    "magento-adobe-commerce": [],
    "amazon-seller-central": ["https://sellingpartnerapi-na.amazon.com/"],
    "ebay-api": ["https://api.ebay.com/"],
    "etsy-api": ["https://openapi.etsy.com/v3/"],
    "square": ["https://connect.squareup.com/v2/"],
    "stripe": ["https://api.stripe.com/v1/"],
    "paypal": ["https://api-m.paypal.com/"],
    "brex": ["https://platform.brexapis.com/v2/"],
    "quickbooks-online": ["https://quickbooks.api.intuit.com/v3/"],
    "xero": ["https://api.xero.com/api.xro/2.0/"],
    "netsuite": [],
    "sap": [],
    "billcom": ["https://api.bill.com/api/v2/"],
    "chargebee": ["https://api.chargebee.com/api/v2/"],
    "recurly": ["https://v3.recurly.com/"],
    "google-workspace-gmail-docs-drive-sheets-calendar": [
        "https://www.googleapis.com/",
        "https://gmail.googleapis.com/",
        "https://drive.googleapis.com/",
        "https://sheets.googleapis.com/",
        "https://docs.googleapis.com/",
        "https://calendar.googleapis.com/",
    ],
    "microsoft-365-outlook-onedrive-sharepoint-excel": ["https://graph.microsoft.com/v1.0/"],
    "airtable": ["https://api.airtable.com/v0/"],
    "calendly": ["https://api.calendly.com/"],
    "docusign": ["https://account-d.docusign.com/"],
    "pandadoc": ["https://api.pandadoc.com/public/v1/"],
    "zoom": ["https://api.zoom.us/v2/"],
    "google-meet": ["https://meet.googleapis.com/"],
}

# Optional relative path for generic connection test GET (under first allowed prefix).
INTEGRATION_DEFAULT_PROBE_PATHS: dict[str, str] = {
    "sendgrid": "/user/profile",
    "stripe": "/balance",
    "github": "/user",
    "gitlab": "/user",
    "slack": "/auth.test",
    "notion": "/users/me",
    "linear": "/graphql",
    "hubspot": "/crm/v3/objects/contacts?limit=1",
    "twilio": "/Accounts.json",
    "whatsapp-business-api": "/me",
    "discord": "/users/@me",
    "airtable": "/meta/whoami",
    "zoom": "/users/me",
}

_CATALOG_SLUGS = {slug for slug, _ in CATALOG_INTEGRATIONS}


def default_prefixes_for_slug(slug: str) -> list[str]:
    key = slug.strip().lower()
    if key in INTEGRATION_DEFAULT_API_PREFIXES:
        return list(INTEGRATION_DEFAULT_API_PREFIXES[key])
    if key.startswith("google-"):
        return list(
            INTEGRATION_DEFAULT_API_PREFIXES[
                "google-workspace-gmail-docs-drive-sheets-calendar"
            ]
        )
    if key in ("microsoft-teams", "microsoft-azure", "dynamics-365"):
        return list(
            INTEGRATION_DEFAULT_API_PREFIXES[
                "microsoft-365-outlook-onedrive-sharepoint-excel"
            ]
        )
    return []


def catalog_slugs_missing_defaults() -> list[str]:
    """Slugs with no default prefix (self-hosted DBs, tenant URLs, etc.)."""
    missing: list[str] = []
    for slug in sorted(_CATALOG_SLUGS):
        if not default_prefixes_for_slug(slug):
            missing.append(slug)
    return missing
