# OAuth walkthrough #13 — Salesforce

Status: **done**

Registry scopes: `api refresh_token`  
Login host: **production** `login.salesforce.com` (Developer Edition and production orgs).  
**Sandbox** orgs use `test.salesforce.com` — URLs in `integration_oauth_registry.py` must match your org type (see §6).

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

## 1. Create an External Client App

You need a Salesforce org (free [Developer Edition](https://developer.salesforce.com/signup) works).

1. Log in → **Setup** (gear) → search **App Manager**
2. **App Manager** → **New External Client App** (not “New Lightning App”)
3. **Basic information**
   - Name: `MultiWorkAgent`
   - API Name: auto-filled
   - Contact Email: your email
4. **API (Enable OAuth Settings)**
   - Enable OAuth Settings: **checked**
   - **Callback URL:**  
     `https://multiworkagent.vercel.app/integrations/oauth/callback`
   - **Selected OAuth Scopes** — move to “Selected”:
     - **Access and manage your data (api)**
     - **Perform requests on your behalf at any time (refresh_token, offline_access)**
   - (Optional later) **Require Proof Key for Code Exchange (PKCE)** — leave **off** unless we add PKCE in code
5. **Save** → **Continue** (warnings about waiting period are normal)

New connected apps can take **2–10 minutes** before OAuth works.

## 2. Credentials (Consumer Key / Client ID)

Same value — Salesforce label **Consumer Key**, our env **`SALESFORCE_OAUTH_CLIENT_ID`**.

1. **Setup** → **App Manager** → find **MultiWorkAgent** (type: External Client App) → click the **app name**
2. Open **Settings** (or **OAuth Settings** / **Consumer Details** — wording varies)
3. Copy **Consumer Key** (sometimes shown as **Client ID** / **OAuth Client ID**) → `.env` `SALESFORCE_OAUTH_CLIENT_ID`
4. For the secret: **Manage Consumer Details** or **Generate Secret** → verify email if prompted → copy **Consumer Secret** → `.env` `SALESFORCE_OAUTH_CLIENT_SECRET`  
   (Secret is often hidden after first view — regenerate if you lost it.)

Quick Find alternates: search **External Client Apps** → select your app → same credential fields.

## 3. Server env (local `.env`)

```env
SALESFORCE_OAUTH_CLIENT_ID=
SALESFORCE_OAUTH_CLIENT_SECRET=
```

Restart Flask after filling values.

**Redirect URI vs `APP_BASE_URL`:** MultiWorkAgent sends `{APP_BASE_URL}/integrations/oauth/callback`. Your `.env` has `http://127.0.0.1:5000` — add this callback in Salesforce **in addition to** the Vercel URL if you test locally:

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

If you only registered the Vercel callback, test Connect on Vercel or add the local URL above.

## 4. Test

1. Open **https://multiworkagent.vercel.app**
2. One **business** selected
3. **Data & integrations** → **Salesforce** → **OAuth**
4. Log in to Salesforce and **Allow** → return to MultiWorkAgent

## 5. Common issues

| Issue | Fix |
|-------|-----|
| `redirect_uri` mismatch | Callback in Connected App must match exactly (HTTPS, no trailing slash on base URL) |
| `invalid_client_id` / app not found | Wait 10 minutes after creating the Connected App; confirm Consumer Key |
| OAuth error right after save | **Manage** → **Edit Policies** → **Permitted Users**: “All users may self-authorize” (or admin-approved users per your policy) |
| Sandbox org (`*.sandbox.my.salesforce.com`) | Registry uses `login.salesforce.com`; for sandbox-only, change authorize/token URLs to `https://test.salesforce.com/services/oauth2/...` in `integration_oauth_registry.py` or use a production/Developer org for this walkthrough |

Doc: [Salesforce OAuth 2.0 Web Server Flow](https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm)

## Next

**#14 HubSpot** — [14-hubspot.md](14-hubspot.md)
