# OAuth walkthrough #5 — Microsoft 365

Status: **done**

Catalog tile: **Microsoft 365 (Outlook, OneDrive, SharePoint, Excel)**  
Registry slug: `microsoft-365-outlook-onedrive-sharepoint-excel`

Also uses **`MICROSOFT_OAUTH_*`** for: Microsoft Teams, Azure, Dynamics 365 (same app is fine if scopes cover them).

## Callback URL

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

## 1. Azure / Entra app registration

1. [Microsoft Entra admin center](https://entra.microsoft.com/) or [Azure Portal](https://portal.azure.com/) → **Microsoft Entra ID** → **App registrations** → **New registration**
2. **Name:** `MultiWorkAgent Integrations (local)`
3. **Supported account types:**  
   - **Accounts in any organizational directory and personal Microsoft accounts** (most flexible for dev), or  
   - Single tenant if you only use one org.
4. **Redirect URI:** Web →  
   `http://127.0.0.1:5000/integrations/oauth/callback`
5. Register → note **Application (client) ID**

## 2. Client secret

1. App → **Certificates & secrets** → **New client secret** → copy **Value** (secret) immediately.

## 3. API permissions

App → **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated**:

- `openid`, `offline_access`, `User.Read`
- `Files.Read.All` (OneDrive)
- `Sites.Read.All` (SharePoint)

Registry scopes match: `openid offline_access User.Read Files.Read.All Sites.Read.All`

Click **Grant admin consent** if your tenant requires it (work/school accounts).

## 4. Server env

```env
MICROSOFT_OAUTH_CLIENT_ID=application_client_id
MICROSOFT_OAUTH_CLIENT_SECRET=secret_value
```

Restart Flask.

## 5. Test

1. One **business** selected  
2. **Data & integrations** → **Microsoft 365 (Outlook, OneDrive, SharePoint, Excel)** → **OAuth**  
3. Sign in with Microsoft → consent → back to app

## 6. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | URI must match Entra app exactly (http vs https, port 5000) |
| AADSTS650053 | Add Graph delegated permissions above |
| **AADSTS16000** + `live.com` / personal account | App is **single-tenant** but you signed in with **personal Microsoft** (@outlook.com). Fix below. |
| Wrong client ID in error (not your app name) | `.env` `MICROSOFT_OAUTH_CLIENT_ID` must be **your** app’s Application (client) ID |

### Fix AADSTS16000 (personal Microsoft account)

1. Entra → **App registrations** → **your** MultiWorkAgent app (not a random/other app).
2. **Authentication** → **Supported account types** → select:  
   **Accounts in any organizational directory (multitenant) and personal Microsoft accounts**  
   ( wording may be “Any Entra ID tenant + personal Microsoft accounts” ).
3. Save → sign out of Microsoft in the browser (or use InPrivate) → try **OAuth** again from MultiWorkAgent.

If you only use **work/school** accounts, keep single-tenant but sign in with that org’s `@company.com` account, not `@outlook.com`.

### Verify you’re using your app

In the error JSON, `clientId` must equal **Application (client) ID** from your registration and match `MICROSOFT_OAUTH_CLIENT_ID` in `.env`.  
If you see another name (e.g. unrelated display name), fix the client ID in `.env` and restart Flask.

## Next

**#6 Slack** — `SLACK_OAUTH_*` (`06-slack.md`)
