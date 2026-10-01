# Integrations — MultiWorkAgent

This app connects to **109 third-party services** (108 from the product catalog plus **Square** for merchant/payments workflows). Each **business workspace** stores its own credentials. The **agent** uses those connections to read, update, and automate work on behalf of that business only.

> **Note:** Subscription billing *for MultiWorkAgent itself* is handled via **Square**. Stripe, PayPal, etc. in the catalog are **integrations the agent can operate** for a customer’s business (invoices, subscriptions, ERP), not the app’s own checkout unless configured separately.

## Architecture (target)

| Layer | Responsibility |
|--------|----------------|
| **Integration catalog** | Static list of supported providers (`integrations_catalog.py`) |
| **Connection store** | Separate DB from chat: encrypted OAuth tokens / API keys per business + provider |
| **Agent tool layer** | Provider-specific tools (e.g. `github.create_pr`, `shopify.update_product`) gated by scopes |
| **Audit log** | Every agent write tagged with business, integration, user/run id |

Businesses **sign up → create workspace → connect integrations →** agent runs consume execution runs against connected systems.

## Agent capabilities

For each connected integration, the agent can (when scopes allow):

- **Read** — list, search, export, summarize (CRM deals, tickets, repo issues, orders, etc.)
- **Write** — create/update/delete records (with pre-run confirmation for destructive ops)
- **Automate** — trigger workflows (Zapier/Make/n8n), CI jobs, deployments, messages

Connections are **never shared** across businesses. Prompt caching can reuse static API docs per provider; credentials stay in the connection store.

## Categories

1. Version Control, CI/CD & Developer Tools (17)
2. CMS, Web Builders & Content Platforms (8)
3. CRM, Sales & Revenue Operations (10)
4. Customer Support & Ticketing (7)
5. Databases, Storage & Vector Search (18)
6. Team Communication & Messaging (9)
7. Project Management & Productivity (10)
8. Workflow Automation & Middleware (4)
9. E-Commerce & Retail (8, includes Square)
10. Financials, Billing & ERP (10)
11. Workspace & Productivity Suites (8)

Source of truth for names and slugs: `integrations_catalog.py`.

## UI

- **Data & integrations** — browse catalog, search, connect via **API key** (any provider) or **OAuth** (where defined in `integration_oauth_registry.py`)

### OAuth setup

See **`INTEGRATIONS_OAUTH.md`** — add providers one at a time in the registry, register OAuth apps on the server, set env vars. Users never paste client IDs.
- **Business workspace** — shows count of connected DBs + integrations
- **Agent** — `@provider` mentions and run inspector list tools invoked

## Implementation status

| Item | Status |
|------|--------|
| Catalog (109 providers) | Done |
| Connection store DB | Done (`integration_connections`) |
| API key connect | Done |
| OAuth registry + generic flow | Done — 19 providers defined; enable each via server env (see INTEGRATIONS_OAUTH.md) |
| Agent tools per provider | Planned |
