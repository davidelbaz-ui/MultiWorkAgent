# OAuth setup order

| # | Provider | Doc | Status |
|---|----------|-----|--------|
| 1 | GitHub | [01-github.md](01-github.md) | done |
| 2 | GitLab | [02-gitlab.md](02-gitlab.md) | done |
| 3 | Bitbucket | [03-bitbucket.md](03-bitbucket.md) | deferred |
| 4 | Google Workspace | [04-google-workspace.md](04-google-workspace.md) | done |
| 5 | Microsoft 365 | [05-microsoft-365.md](05-microsoft-365.md) | done |
| 6 | Slack | [06-slack.md](06-slack.md) | done |
| 7 | Jira | [07-jira.md](07-jira.md) | done |
| 8 | Confluence | [08-confluence.md](08-confluence.md) | done |
| 9 | Notion | [09-notion.md](09-notion.md) | done |
| 10 | Linear | [10-linear.md](10-linear.md) | done |
| 11 | Asana | [11-asana.md](11-asana.md) | done |
| 12 | Discord | [12-discord.md](12-discord.md) | done |
| 13 | Salesforce | [13-salesforce.md](13-salesforce.md) | done |
| 14 | HubSpot | [14-hubspot.md](14-hubspot.md) | done |
| 15 | Stripe | [15-stripe.md](15-stripe.md) | done |
| 16 | QuickBooks Online | [16-quickbooks-online.md](16-quickbooks-online.md) | done |
| 17 | Xero | [17-xero.md](17-xero.md) | done |
| 18 | Zoom | [18-zoom.md](18-zoom.md) | done |
| 19 | Airtable | [19-airtable.md](19-airtable.md) | done |

**Wired OAuth walkthrough complete** (registry `_WIRED_OAUTH`). **Bitbucket (#3)** remains deferred. Other catalog slugs still need URLs in `integration_oauth_registry.py` or API-key connect.

Callback for all integrations: `{APP_BASE_URL}/integrations/oauth/callback`

**Production (operator):** register `https://multiworkagent.vercel.app/integrations/oauth/callback` and set Vercel `APP_BASE_URL=https://multiworkagent.vercel.app`.
