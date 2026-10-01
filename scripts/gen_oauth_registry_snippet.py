"""One-off helper to emit catalog constants for integration_oauth_registry.py."""

from integrations_catalog import INTEGRATION_CATEGORIES

ENV_OVERRIDES = {
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

WIRED = frozenset(
    {
        "github",
        "gitlab",
        "bitbucket",
        "google-workspace-gmail-docs-drive-sheets-calendar",
        "microsoft-365-outlook-onedrive-sharepoint-excel",
        "slack",
        "jira",
        "confluence",
        "notion",
        "linear",
        "asana",
        "discord",
        "salesforce",
        "hubspot",
        "stripe",
        "quickbooks-online",
        "xero",
        "zoom",
        "airtable",
    }
)


def main() -> None:
    lines: list[str] = []
    lines.append("CATALOG_INTEGRATIONS: list[tuple[str, str]] = [")
    for category in INTEGRATION_CATEGORIES:
        for item in category["integrations"]:
            lines.append(f"    ({item['slug']!r}, {item['name']!r}),")
    lines.append("]")
    print("\n".join(lines))
    print("\n# unique env pairs:", len(set(ENV_OVERRIDES.values())))


if __name__ == "__main__":
    main()
