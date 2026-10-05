# Square billing (MultiWorkAgent subscriptions & invoices)

This app bills **your customers for MultiWorkAgent** (Starter / Pro plans) through **Square**. That uses **server env vars** (`SQUARE_*` below). It is separate from connecting **Square as a business integration** so the agent can operate a merchant’s Square account (`SQUARE_OAUTH_*` in the integration catalog).

When billing is configured, the **Billing** page offers Square checkout, webhooks update subscription status and quotas, and owners can **Sync from Square** for invoices.

## What you need

| Piece | Purpose |
|-------|---------|
| Square Developer application | Access token + webhook signature key |
| Square location | `SQUARE_LOCATION_ID` (same environment as token) |
| Subscription plan variations | Starter ($19/mo, 50 runs) and Pro ($49/mo, 200 runs) |
| Public HTTPS app URL | `APP_BASE_URL` + webhook endpoint |

Local testing without Square: set `BILLING_DEV_MOCK=1` (or `SQUARE_MOCK=1`). Subscribe on Billing activates plans and a sample invoice in the database only.

## 1. Square Developer Dashboard

1. Open [Square Developer](https://developer.squareup.com/apps) and create or select an application.
2. **Credentials**
   - **Sandbox** (testing): copy **Sandbox access token**.
   - **Production**: complete Square account verification, then copy **Production access token**.
3. Set in `.env` / Vercel:
   - `SQUARE_ACCESS_TOKEN`
   - `SQUARE_ENVIRONMENT=sandbox` or `production`

## 2. Location ID

In [Square Dashboard](https://squareup.com/dashboard) (sandbox or production matching your token):

- **Account & Settings → Locations** (or Locations in sandbox seller dashboard).
- Copy the location ID → `SQUARE_LOCATION_ID`.

All checkout and invoice search calls are scoped to this location.

## 3. Subscription plans (Starter & Pro)

Plans are defined in code (`subscription_plans.py`): **Starter** and **Pro** with monthly quotas. Square must have matching **subscription plan variations**.

1. In Square Dashboard, enable **Subscriptions** for your business (Square Subscriptions product).
2. Create two subscription plans aligned with your pricing (e.g. $19/mo and $49/mo).
3. Obtain each plan’s **subscription plan variation ID** (Square Dashboard plan details, or Subscriptions/Catalog API).

Set:

```env
SQUARE_STARTER_PLAN_VARIATION_ID=
SQUARE_PRO_PLAN_VARIATION_ID=
```

**Alternative:** pre-built Square payment links (no variation IDs):

```env
SQUARE_CHECKOUT_URL_STARTER=https://...
SQUARE_CHECKOUT_URL_PRO=https://...
```

If a static URL is set and the variation ID for that tier is empty, checkout redirects there with `reference_id=<account_id>`.

## 4. App URL and checkout return

Set **`APP_BASE_URL`** to your public site (no trailing slash):

```env
APP_BASE_URL=https://multiworkagent.vercel.app
```

After payment, Square redirects to `{APP_BASE_URL}/billing?checkout=done`. The app creates a Square **customer** per account and a **payment link** with your plan variation.

Optional: `SQUARE_SUPPORT_EMAIL` for checkout receipts.

## 5. Webhooks (subscriptions + invoices)

Square must notify your app when subscriptions and invoices change.

1. Developer Dashboard → your app → **Webhooks**.
2. **Notification URL** (must match env **character for character**):

   ```text
   https://multiworkagent.vercel.app/webhooks/square
   ```

3. Subscribe to events including:
   - `subscription.created`, `subscription.updated`, …
   - `invoice.created`, `invoice.updated`, `invoice.published`, …

4. Copy the **Signature key** → `SQUARE_WEBHOOK_SIGNATURE_KEY`.

5. Set (recommended, same URL as in Square):

   ```env
   SQUARE_WEBHOOK_NOTIFICATION_URL=https://multiworkagent.vercel.app/webhooks/square
   ```

If `SQUARE_WEBHOOK_NOTIFICATION_URL` is empty, the app derives the URL from `APP_BASE_URL`. Signature verification uses this URL plus the raw POST body—if Square’s registered URL and your env differ, webhooks return **401 invalid signature**.

Production **requires** `SQUARE_WEBHOOK_SIGNATURE_KEY` when `APP_ENV=production`.

## 6. Vercel env checklist

Add for **Production** (then **Redeploy**):

| Variable | Example / notes |
|----------|-----------------|
| `APP_BASE_URL` | `https://multiworkagent.vercel.app` |
| `SQUARE_ACCESS_TOKEN` | Production or sandbox token |
| `SQUARE_LOCATION_ID` | From Square locations |
| `SQUARE_ENVIRONMENT` | `production` or `sandbox` |
| `SQUARE_STARTER_PLAN_VARIATION_ID` | From Subscriptions |
| `SQUARE_PRO_PLAN_VARIATION_ID` | From Subscriptions |
| `SQUARE_WEBHOOK_SIGNATURE_KEY` | From Developer → Webhooks |
| `SQUARE_WEBHOOK_NOTIFICATION_URL` | Full webhook URL |
| `SQUARE_SUPPORT_EMAIL` | Optional |

Do **not** set `BILLING_DEV_MOCK=1` on production.

## 7. Verify end-to-end

1. Open **Billing** as account **owner** — banner should not say “Square is not configured”.
2. Click **Subscribe** on Starter or Pro → Square checkout opens.
3. Complete sandbox payment → return to Billing with “Checkout complete…” → after webhook, plan and usage quota update.
4. **Invoices (Square)** → **Sync from Square** (requires a linked Square customer after checkout).

Webhook events are stored in `square_webhook_events` (idempotent by `event_id`).

## 8. Catalog “Square” integration (agent)

To let the **agent** call Square **on behalf of a business** (orders, catalog, etc.), use **Data & integrations → Square** and operator `SQUARE_OAUTH_CLIENT_ID` / `SQUARE_OAUTH_CLIENT_SECRET`. That does not replace `SQUARE_ACCESS_TOKEN` for **your** SaaS billing.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Billing page: “Square is not configured” | Token + location + at least one plan variation ID or checkout URL |
| Checkout 400 from API | Variation IDs, location, token environment mismatch |
| Plan stays pending after payment | Webhooks URL/signature key; Vercel logs for `/webhooks/square` |
| Sync invoices: no customer | Complete checkout once so `square_customer_id` is saved |
| 401 on webhook | `SQUARE_WEBHOOK_NOTIFICATION_URL` exactly matches Square dashboard |

Implementation: `square_billing.py`, `subscription_store.py`, `invoice_store.py`, `static/billing.js`.
