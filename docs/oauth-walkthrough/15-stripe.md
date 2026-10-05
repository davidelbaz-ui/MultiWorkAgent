# OAuth walkthrough #15 — Stripe (Connect)

Status: **done**

Registry uses **Stripe Connect** OAuth (`read_write` scope).  
This is **not** the same as **Square** billing vars (`SQUARE_*`) for MultiWorkAgent subscriptions.

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Add `http://127.0.0.1:5000/integrations/oauth/callback` in Stripe if you test locally with that `APP_BASE_URL`.

## 1. Stripe Connect OAuth settings

1. [Stripe Dashboard](https://dashboard.stripe.com/) (use **Test mode** toggle while developing)
2. **Settings** (gear) → **Connect** → **OAuth settings**  
   Or: **Connect** → **Settings** → **Integration** / **OAuth**
3. **Redirect URIs** → add the callback URL(s) above → **Save**
4. Copy **Test client ID** (`ca_…`) from this OAuth page → `STRIPE_OAUTH_CLIENT_ID`
5. **Developers → API keys** → **Secret key** (`sk_test_…`) → `STRIPE_OAUTH_CLIENT_SECRET`  
   (Stripe has no separate OAuth client secret — see step 2 in this doc.)

If you don’t see Connect OAuth yet, enable **Connect** on your account (Stripe may ask you to complete platform profile).

## 2. Credentials (no separate “OAuth secret”)

Stripe Connect only shows a **Client ID** on the OAuth page (`ca_…`, test or live).

For token exchange, Stripe uses your platform **Secret API key** as `client_secret` (same test/live mode as the client ID).

1. **Settings → Connect → Onboarding options → OAuth** → copy **Test client ID** (sandbox) or **Live client ID**
2. **Developers** (bottom left) → **API keys** → reveal **Secret key** (`sk_test_…` in sandbox, `sk_live_…` in production)

Local `.env`:

```env
STRIPE_OAUTH_CLIENT_ID=ca_...
STRIPE_OAUTH_CLIENT_SECRET=sk_test_...
```

Use **test** client ID + **test** secret together (sandbox banner). Never commit live secret keys.

Restart Flask.

## 3. Test

1. Open app at URL matching registered redirect (`APP_BASE_URL`)
2. One **business** selected
3. **Data & integrations** → **Stripe** → **OAuth**
4. Complete Stripe Connect authorization

## 4. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | Redirect URI in Stripe Connect settings must match exactly |
| No OAuth client secret on page | Normal — use **Secret API key** (`sk_test_` / `sk_live_`) as `STRIPE_OAUTH_CLIENT_SECRET` |
| Test vs live | Test-mode Connect credentials only work in test mode |
| Confused with Square | `SQUARE_*` = bill for MultiWorkAgent; `STRIPE_OAUTH_*` = connect a business’s Stripe |

Doc: [Connect OAuth reference](https://docs.stripe.com/connect/oauth-reference)

## Next

**#16 QuickBooks Online** — [16-quickbooks-online.md](16-quickbooks-online.md)
