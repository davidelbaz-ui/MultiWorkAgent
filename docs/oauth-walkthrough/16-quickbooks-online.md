# OAuth walkthrough #16 — QuickBooks Online

Status: **done**

Registry scope: `com.intuit.quickbooks.accounting`

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Add `http://127.0.0.1:5000/integrations/oauth/callback` for local Flask if needed.

**Privacy policy URL (App details / Intuit compliance):**

```text
https://multiworkagent.vercel.app/privacy-policy
```

**EULA (App details):**

```text
https://multiworkagent.vercel.app/licence-agreement
```

## Production keys (required for real QuickBooks companies)

Intuit **does not** promote Development keys to Production. **Show credentials** for Production stays locked until **App details** and **Compliance** are complete and Intuit finishes review.

### Step 1 — App details (100%)

- Privacy policy, EULA, host `multiworkagent.vercel.app`, URLs, categories, hosting, etc.
- Pages must be **live on HTTPS** (deploy to Vercel so Intuit can fetch them).

### Step 2 — Compliance (~40 min + Intuit review)

1. Open **Compliance** in the app dashboard (left sidebar).
2. Complete the **Compliance checklist** and **App Assessment Questionnaire** (security, data use, OAuth, encryption, incident response — answer for MultiWorkAgent as a private platform app connecting your customers’ QBO).
3. Submit. Status moves from review → approved when Intuit issues **Production** credentials (often **several business days**, not instant).

You do **not** need a public QuickBooks App Store listing for a **private** app used by your own platform—but you **do** need the assessment for Production keys.

### Step 3 — Production redirect URI + credentials

After Production unlocks:

1. **Keys & OAuth** → **Production** tab (not Development).
2. Add redirect URI: `https://multiworkagent.vercel.app/integrations/oauth/callback`
3. **Show credentials** → copy **Production** Client ID + secret → `.env`:

```env
QUICKBOOKS_OAUTH_CLIENT_ID=
QUICKBOOKS_OAUTH_CLIENT_SECRET=
```

4. Redeploy Vercel with the same values if OAuth runs on production.
5. Connect from **https://multiworkagent.vercel.app** → real QBO company (not sandbox).

### If Production stays locked

- Compliance still **0%** or **Requires attention** → fix questionnaire / security answers.
- Legal URLs return 404 → deploy latest code to Vercel first.
- Open [Intuit Developer Support](https://help.developer.intuit.com/) with your **App ID** if assessment is submitted but keys never appear.

## 1. Create an Intuit app

1. [Intuit Developer](https://developer.intuit.com/) → sign in
2. **Dashboard** → **Create an app** → **QuickBooks Online and Payments**
3. App name: `MultiWorkAgent`
4. **Keys & OAuth** (or **Production** / **Development** keys tabs):
   - **Redirect URIs** → add callback URL(s) above → **Save**
   - **Scopes:** enable **Accounting** (`com.intuit.quickbooks.accounting`)

Use **Development** keys only for sandbox companies. For **production** QBO, complete Compliance and use **Production** keys (section above).

## 2. Credentials

On **Keys & OAuth**:

- **Production** (live QBO): Client ID + secret after Compliance approval
- **Development** (sandbox only): separate Client ID + secret

Both map to the same `.env` names — use **one pair at a time** (Production for your goal).

## 3. Local `.env`

```env
QUICKBOOKS_OAUTH_CLIENT_ID=
QUICKBOOKS_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 4. Test

1. Open app at URL matching registered redirect (`APP_BASE_URL`)
2. One **business** selected
3. **Data & integrations** → **QuickBooks Online** → **OAuth**
4. Sign in to Intuit / pick a sandbox company → **Connect**

## 5. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | URI in Intuit app must match `{APP_BASE_URL}/integrations/oauth/callback` |
| Wrong environment | Development client + sandbox company; production keys for live QBO |
| invalid_scope | Add Accounting scope on the Intuit app |

Doc: [Intuit OAuth 2.0](https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0)

## Next

**#17 Xero** — [17-xero.md](17-xero.md)
