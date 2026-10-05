# OAuth walkthrough #14 — HubSpot

Status: **done**

Registry scopes: `crm.objects.contacts.read crm.objects.deals.read`

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

HubSpot **project-based apps** require **HTTPS** redirect URLs (except `http://localhost` for dev — not `127.0.0.1`). For local Flask, use Vercel for Connect or test with `http://localhost:5000/...` if you add that redirect in the app config.

## Legacy apps unavailable?

If **Settings → Legacy Apps** says legacy apps aren’t on your account, use a **project-based app** (below). Do **not** use **Create a service key** for MultiWorkAgent OAuth — that’s API-key style, not the Connect → OAuth flow.

## 1. Create a project-based app

Your account uses the **HubSpot CLI** (no Legacy Apps).

**If you already have `MultiWorkAgentHS` with only `hsproject.json`:** add `src/app/app-hsmeta.json` (OAuth redirect + scopes), then upload (see step 2).

**New project from scratch:**

```powershell
npm i -g @hubspot/cli
hs account auth
cd $env:USERPROFILE\Documents
hs project create --name MultiWorkAgent --project-base app --distribution private --auth oauth
```

Edit `src/app/app-hsmeta.json` → set `auth.redirectUrls` to the callback below and scopes to match the registry.

**Do not** use **Create a service key** — that is not OAuth Connect.

## 2. Upload project + get credentials

From your HubSpot project folder (e.g. `C:\Users\david\MultiWorkAgentHS`):

```powershell
hs project upload
hs project open
```

In the browser: **Project → app component → Auth** → **Client credentials** → copy into `.env`:

```env
HUBSPOT_OAUTH_CLIENT_ID=
HUBSPOT_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 3. Credentials (reference)

Same as step 2: **Development** → **Projects** → **MultiWorkAgent** → app → **Auth** tab.

## 4. Test

1. Open the app at the same base URL as your registered redirect (`APP_BASE_URL`)
2. One **business** selected
3. **Data & integrations** → **HubSpot** → **OAuth**

## 5. Common issues

| Issue | Fix |
|-------|-----|
| Legacy apps not available | Use **project-based app** + **Auth** tab credentials |
| redirect_uri mismatch | Redirect in project app must match `{APP_BASE_URL}/integrations/oauth/callback` |
| Used service key by mistake | Service keys ≠ OAuth; create project app with OAuth auth |
| scope errors | Add CRM read scopes in project app config |

Doc: [Working with OAuth](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/oauth/working-with-oauth)

## Next

**#15 Stripe Connect** — [15-stripe.md](15-stripe.md)
