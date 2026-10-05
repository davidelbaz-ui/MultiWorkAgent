# OAuth walkthrough #17 — Xero

Status: **done**

Registry scopes (sent on authorize):

`openid profile email accounting.transactions accounting.settings offline_access`

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Add `http://127.0.0.1:5000/integrations/oauth/callback` for local Flask if needed.

**Privacy policy (Xero app setup):**

```text
https://multiworkagent.vercel.app/privacy-policy
```

## 1. Create a Xero app

1. [Xero Developer](https://developer.xero.com/) → sign in → **My apps**
2. **New app** → **Web app** (OAuth 2.0)
3. **App name:** `MultiWorkAgent`
4. **Company or application URL:** `https://multiworkagent.vercel.app`
5. **OAuth 2.0 redirect URI:** callback URL above (+ local if needed)
6. **Scopes:** enable at least those in the registry (Accounting transactions, Accounting settings, OpenID, offline access)

## 2. Credentials

On the app **Configuration** page:

- **Client ID** → `XERO_OAUTH_CLIENT_ID`
- **Client secret** (Generate if needed) → `XERO_OAUTH_CLIENT_SECRET`

## 3. Local `.env`

```env
XERO_OAUTH_CLIENT_ID=
XERO_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 4. Test

1. Open app at URL matching registered redirect (`APP_BASE_URL`)
2. One **business** selected
3. **Data & integrations** → **Xero** → **OAuth**
4. Sign in to Xero and authorize the organisation

## 5. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | Redirect URI in Xero must match `{APP_BASE_URL}/integrations/oauth/callback` exactly |
| invalid_scope | Add accounting + openid + offline_access scopes on the Xero app |
| No org connected | User must grant access to at least one Xero organisation |

Doc: [Xero OAuth 2.0](https://developer.xero.com/documentation/guides/oauth2/overview/)

## Next

**#18 Zoom** — [18-zoom.md](18-zoom.md)
