# Integration OAuth — one provider at a time

MultiWorkAgent uses **platform OAuth apps** (your server env vars). End users only click **Connect → OAuth** and approve access. Tokens are stored encrypted per business in `integration_connections`.

Callback URL for every provider:

```text
{APP_BASE_URL}/integrations/oauth/callback
```

| Environment | Callback URL |
|-------------|--------------|
| Production (Vercel) | `https://multiworkagent.vercel.app/integrations/oauth/callback` |
| Local dev | `http://127.0.0.1:5000/integrations/oauth/callback` |

Set **`APP_BASE_URL=https://multiworkagent.vercel.app`** on Vercel so Connect sends the same redirect URI you registered in each provider console.

Use a **different OAuth client** than Google login (`GOOGLE_LOGIN_*`). Integration Google uses `GOOGLE_OAUTH_*`.

---

## Where definitions live

| File | Purpose |
|------|---------|
| `integration_oauth_catalog_data.py` | All **109** catalog `(slug, name)` pairs |
| `integration_oauth_registry.py` | Env var names for every slug; OAuth URLs in `_WIRED_OAUTH` (19 wired today) |
| `integration_oauth_hints.py` | Optional: fetch login/email for credential hint after connect |
| `integrations_catalog.py` | Product catalog (must stay in sync with catalog data) |
| `integration_oauth.py` | Generic authorize + token exchange |
| `.env.example` | Commented `*_OAUTH_CLIENT_ID` / `SECRET` for all 109 (regenerate via `scripts/gen_env_oauth_example.py`) |

List env keys in Python:

```python
from integration_oauth_registry import list_env_keys_table
for row in list_env_keys_table():
    print(row["slug"], row["client_id_env"])
```

---

## Checklist: enable OAuth for provider #N

1. **Confirm catalog slug** in `integrations_catalog.py` (e.g. `shopify`).

2. **Add** `OAuthProviderTemplate(...)` to `OAUTH_PROVIDERS` in `integration_oauth_registry.py`:
   - `authorize_url`, `token_url`, `scopes` from vendor docs
   - `client_id_env` / `client_secret_env` (unique pair per vendor app, reuse pair if same app covers Jira + Confluence)
   - `authorize_extra` if needed (Google: `access_type=offline`, Atlassian: `audience=...`)
   - `token_auth="basic"` only if vendor requires Basic auth on token endpoint (Notion)

3. **Register OAuth app** in the vendor developer console; set redirect URI to your callback URL.

4. **Set env** on the server (see `.env.example`), restart the app.

5. **(Optional)** Add hint logic in `integration_oauth_hints.py` for nicer “connected as …” labels.

6. **Test**: Data & integrations → select business → provider → OAuth.

7. **Later**: Agent tools that read `connection_store.get_connection_credentials()`.

---

## Providers with OAuth definitions today

Run in Python to list env vars:

```python
from integration_oauth_registry import env_vars_for_deploy_docs
import json
print(json.dumps(env_vars_for_deploy_docs(), indent=2))
```

Shared env pairs:

| Env vars | Catalog slugs |
|----------|----------------|
| `GITHUB_OAUTH_*` | GitHub |
| `GITLAB_OAUTH_*` | GitLab |
| `BITBUCKET_OAUTH_*` | Bitbucket |
| `GOOGLE_OAUTH_*` | Google Workspace |
| `MICROSOFT_OAUTH_*` | Microsoft 365 |
| `SLACK_OAUTH_*` | Slack |
| `ATLASSIAN_OAUTH_*` | Jira, Confluence |
| `NOTION_OAUTH_*` | Notion |
| `LINEAR_OAUTH_*` | Linear |
| `ASANA_OAUTH_*` | Asana |
| `DISCORD_OAUTH_*` | Discord |
| `SALESFORCE_OAUTH_*` | Salesforce |
| `HUBSPOT_OAUTH_*` | HubSpot |
| `STRIPE_OAUTH_*` | Stripe (Connect) |
| `QUICKBOOKS_OAUTH_*` | QuickBooks Online |
| `XERO_OAUTH_*` | Xero |
| `ZOOM_OAUTH_*` | Zoom |
| `AIRTABLE_OAUTH_*` | Airtable |

Until env vars are set, the UI still offers **API key** for every catalog entry.

---

## Special cases (add when you reach them)

- **Shopify, Zendesk, Salesforce sandbox**: extra subdomain/instance fields before authorize — extend connect UI + store in credentials JSON.
- **OAuth 1.0a** (some legacy APIs): separate flow, not the generic template.
- **Token refresh**: store `refresh_token` (already saved when returned); add refresh job per provider as needed.

---

## API

- `GET /api/integrations/catalog` — each item includes `auth_methods`, `oauth_available`, `oauth_configured`
- `GET /api/integrations/oauth/providers` — all registry entries + configured flag
- `POST /api/businesses/<id>/integrations/oauth/start` — `{ "provider_slug": "..." }`
