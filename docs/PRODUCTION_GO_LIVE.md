# Production go-live: Claude agent + Square billing

Use this checklist on **Vercel → MultiWorkAgent → Settings → Environment Variables (Production)**.  
Never commit API keys or tokens to git.

Public site: **https://multiworkagent.com**  
After every env change: **Redeploy** production.

Verify: **https://multiworkagent.com/health** and **Admin → System** (agent/billing flags).

---

## 1. Base URL (required for Square webhooks & OAuth)

| Variable | Value |
|----------|--------|
| `APP_BASE_URL` | `https://multiworkagent.com` |
| `APP_ENV` | `production` |
| `FLASK_SECRET_KEY` | long random string |
| `DATABASE_URL` or `POSTGRES_URL` | Vercel Postgres (remote host, not `127.0.0.1`) |

---

## 2. Claude agent (Anthropic)

1. [console.anthropic.com](https://console.anthropic.com/) → **API keys** → create key (`sk-ant-…`).
2. Add billing/credits in Anthropic if needed.

| Variable | Value |
|----------|--------|
| `AGENT_PROVIDER` | `anthropic` |
| `ANTHROPIC_API_KEY` | your `sk-ant-…` key |
| `AGENT_MODEL` | optional; default `claude-sonnet-4-20250514` |
| `AGENT_MOCK` | `0` |

**Important:** If `GEMINI_API_KEY` is still set, you **must** set `AGENT_PROVIDER=anthropic` or the app may use Gemini.

**Limitation:** Integration/database **tools** (Slack, Salesforce, etc.) run on **Gemini** only today. Claude is chat + knowledge context without live tool loop.

**Test:** Send a message on **Agent**. `/health` → `deployment.agent.ready: true`.

Details: [AGENT_CLAUDE.md](AGENT_CLAUDE.md)

---

## 3. Square billing (subscriptions)

Square bills **your customers** for MultiWorkAgent plans. This is **not** the Square **integration** on Data (merchant OAuth).

### 3.1 Credentials

[Square Developer](https://developer.squareup.com/apps) → your app:

| Variable | Notes |
|----------|--------|
| `SQUARE_ACCESS_TOKEN` | Sandbox token for testing; production token when live |
| `SQUARE_ENVIRONMENT` | `sandbox` or `production` |
| `SQUARE_LOCATION_ID` | Square Dashboard → Locations |
| `SQUARE_WEBHOOK_SIGNATURE_KEY` | Developer → Webhooks → signature key |
| `SQUARE_WEBHOOK_NOTIFICATION_URL` | `https://multiworkagent.com/webhooks/square` (must match Square dashboard **exactly**) |

Optional: `SQUARE_SUPPORT_EMAIL` for checkout receipts.

### 3.2 Plans (match `subscription_plans.py`)

Create **Subscriptions** in Square at these prices (monthly + annual per tier):

| Plan | Monthly | Annual (20% off 12× monthly) | Runs/mo |
|------|---------|--------------------------------|---------|
| Starter | $199.99 | $1,919.90/yr | 300 |
| Pro | $299.99 | $2,879.90/yr | 1,000 |
| Max | $399.99 | $3,839.90/yr | 2,000 |
| Enterprise | $499.99 | $4,799.90/yr | 5,000 |

Copy each plan **variation ID** into Vercel:

```env
SQUARE_STARTER_PLAN_VARIATION_ID=
SQUARE_STARTER_ANNUAL_PLAN_VARIATION_ID=
SQUARE_PRO_PLAN_VARIATION_ID=
SQUARE_PRO_ANNUAL_PLAN_VARIATION_ID=
SQUARE_MAX_PLAN_VARIATION_ID=
SQUARE_MAX_ANNUAL_PLAN_VARIATION_ID=
SQUARE_ENTERPRISE_PLAN_VARIATION_ID=
SQUARE_ENTERPRISE_ANNUAL_PLAN_VARIATION_ID=
```

**Or** use pre-built payment links instead of variation IDs (see [SQUARE_BILLING.md](SQUARE_BILLING.md)).

Do **not** set `BILLING_DEV_MOCK=1` on production.

### 3.3 Webhooks

Developer → Webhooks → notification URL:

```text
https://multiworkagent.com/webhooks/square
```

Subscribe to subscription and invoice events (see [SQUARE_BILLING.md](SQUARE_BILLING.md)).

### 3.4 Verify

1. **Billing** as account owner — no “Square is not configured”.
2. **Subscribe** (sandbox card) → return to `/billing?checkout=done` → plan updates after webhook.
3. `/health` → `deployment.billing.mode: "square"`.

Full reference: [SQUARE_BILLING.md](SQUARE_BILLING.md)

---

## 4. Quick health JSON

```json
"deployment": {
  "agent": { "provider": "anthropic", "ready": true, "mock": false, "model": "..." },
  "billing": { "mode": "square", "access_token_set": true, ... }
}
```

If `ready` or `mode` is wrong, fix env and redeploy.
