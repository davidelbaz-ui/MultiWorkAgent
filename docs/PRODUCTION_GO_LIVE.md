# Production go-live: Gemini agent + Square billing

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

## 2. Gemini agent (Google)

1. [Google AI Studio](https://aistudio.google.com/apikey) → create an API key.
2. Enable billing/quotas in Google Cloud if required for your usage tier.

| Variable | Value |
|----------|--------|
| `AGENT_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | your API key |
| `AGENT_MODEL` | optional; default `gemini-3.8-flash` |
| `AGENT_MODEL_FALLBACK` | optional; default `gemini-2.5-flash` |
| `AGENT_MOCK` | `0` |

**Important:** If `ANTHROPIC_API_KEY` is still set, keep **`AGENT_PROVIDER=gemini`** (or unset Anthropic) so the app does not auto-select Claude.

**Tools:** Integration/database **tools** (Slack, Salesforce, etc.) require Gemini with one business selected in the header.

**Test:** Send a message on **Agent**. `/health` → `deployment.agent.provider: "gemini"`, `ready: true`.

Details: [AGENT_GEMINI.md](AGENT_GEMINI.md). Optional Claude-only chat: [AGENT_CLAUDE.md](AGENT_CLAUDE.md)

---

## 3. Square billing (subscriptions)

Stripe bills **your customers** for MultiWorkAgent plans. This is **not** the Stripe **integration** on Data (merchant OAuth).

### 3.1 Credentials

[Stripe Dashboard](https://dashboard.stripe.com/) → Developers:

| Variable | Notes |
|----------|--------|
| `STRIPE_SECRET_KEY` | Test or live secret key |
| `STRIPE_WEBHOOK_SECRET` | Webhooks → signing secret for `/webhooks/stripe` |

### 3.2 Plans (match `subscription_plans.py`)

Create **Products** with recurring **Prices** (monthly + annual per tier):

| Plan | Monthly | Annual (20% off 12× monthly) | Runs/mo |
|------|---------|--------------------------------|---------|
| Starter | $499.00 | $4,790.40/yr | 300 |
| Pro | $1,199.00 | $11,510.40/yr | 1,000 |
| Max | $2,199.00 | $21,134.40/yr | 2,000 |
| Enterprise | $4,999.00 | $47,990.40/yr | 5,000 |

Copy each **Price ID** (`price_…`) into Vercel:

```env
STRIPE_STARTER_MONTHLY_PRICE_ID=
STRIPE_STARTER_ANNUAL_PRICE_ID=
STRIPE_PRO_MONTHLY_PRICE_ID=
STRIPE_PRO_ANNUAL_PRICE_ID=
STRIPE_MAX_MONTHLY_PRICE_ID=
STRIPE_MAX_ANNUAL_PRICE_ID=
STRIPE_ENTERPRISE_MONTHLY_PRICE_ID=
STRIPE_ENTERPRISE_ANNUAL_PRICE_ID=
```

**Or** use hosted Checkout links (see [STRIPE_BILLING.md](STRIPE_BILLING.md)).

Do **not** set `BILLING_DEV_MOCK=1` on production.

### 3.3 Webhooks

Developers → Webhooks → endpoint:

```text
https://multiworkagent.com/webhooks/stripe
```

Subscribe to checkout, subscription, invoice, and charge events (see [STRIPE_BILLING.md](STRIPE_BILLING.md)).

### 3.4 Verify

1. **Billing** as account owner — no “Stripe is not configured”.
2. **Subscribe** (test card) → return to `/billing?checkout=done` → plan updates after webhook.
3. `/health` → `deployment.billing.mode: "stripe"`.

Full reference: [STRIPE_BILLING.md](STRIPE_BILLING.md)

---

## 4. Quick health JSON

```json
"deployment": {
  "agent": { "provider": "gemini", "ready": true, "mock": false, "model": "..." },
  "billing": { "mode": "stripe", "secret_key_set": true, ... }
}
```

If `ready` or `mode` is wrong, fix env and redeploy.
