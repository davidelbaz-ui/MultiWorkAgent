# Stripe billing (MultiWorkAgent subscriptions)

This app bills **your customers** for MultiWorkAgent (Starter, Pro, Max, Enterprise) through **Stripe** using server env vars (`STRIPE_*`). That is separate from connecting **Stripe as a business integration** so the agent can call a merchant’s Stripe account (`STRIPE_OAUTH_*` in the integration catalog).

## Quick checklist

| Item | Env / dashboard |
|------|-----------------|
| Secret API key | `STRIPE_SECRET_KEY` (test or live) |
| Products & prices | Recurring prices per tier → `STRIPE_*_MONTHLY_PRICE_ID` / `STRIPE_*_ANNUAL_PRICE_ID` |
| Webhook | `STRIPE_WEBHOOK_SECRET` + endpoint `https://your-domain/webhooks/stripe` |

Local testing without Stripe: `BILLING_DEV_MOCK=1` (or `STRIPE_MOCK=1`).

## 1. Stripe Dashboard

1. [Stripe Dashboard](https://dashboard.stripe.com/) → **Developers** → API keys → copy **Secret key** → `STRIPE_SECRET_KEY`.
2. **Products** → create one product per tier with **monthly** and **annual** recurring prices.
3. Copy each **Price ID** (`price_…`) into env:

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

**Or** use hosted Checkout links instead of price IDs:

```env
STRIPE_CHECKOUT_URL_STARTER=
STRIPE_CHECKOUT_URL_STARTER_ANNUAL=
# … PRO, MAX, ENTERPRISE
```

## 2. Webhooks

1. Developers → **Webhooks** → Add endpoint: `https://multiworkagent.com/webhooks/stripe`
2. Events: `checkout.session.completed`, `customer.subscription.*`, `invoice.*`, `charge.succeeded`, `charge.refunded`
3. Copy **Signing secret** → `STRIPE_WEBHOOK_SECRET`

Production (`APP_ENV=production`) requires `STRIPE_WEBHOOK_SECRET`.

Checkout sessions request **`payment_method_types: card`** (or optional `STRIPE_PAYMENT_METHOD_CONFIGURATION=pmc_…` from Dashboard). Do **not** use `automatic_payment_methods` on Checkout—that parameter is for PaymentIntents only. **Apple Pay** and **Google Pay** are not separate API types; they appear on hosted Checkout when enabled under [Payment methods](https://dashboard.stripe.com/settings/payment_methods) and the customer’s browser/device supports them.

## 3. Customer flow

1. Account **owner** opens **Billing & usage** → chooses plan → Stripe Checkout.
2. On success, webhooks activate the subscription and sync invoices.
3. **Refresh invoices** calls Stripe list-invoices for the linked customer.

Customer and subscription IDs are stored in `stripe_customer_id` / `stripe_subscription_id`.

Webhook idempotency uses table `stripe_webhook_events` (Stripe `evt_…` ids).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Checkout: no valid payment method types | Enable **Card** for your currency in Dashboard payment methods, or set `STRIPE_PAYMENT_METHOD_CONFIGURATION` |
| Checkout: unknown `automatic_payment_methods` | Remove that param from Checkout; app uses `payment_method_types` / PMC instead |
| Billing page 503 | `STRIPE_SECRET_KEY` + at least one price ID or checkout URL per tier |
| Plan stays pending | Webhook secret; Vercel logs for `/webhooks/stripe` |
| 401 on webhook | Wrong signing secret or proxy altered body |
| Sync invoices: no customer | Complete checkout once |

Implementation: `stripe_billing.py`, `subscription_store.py`, `invoice_store.py`, `static/billing.js`.
