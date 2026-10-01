# OAuth walkthrough #10 — Linear

Status: **done**

## Callback URL

Use the same host you use for other integrations (usually):

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

## 1. Create an OAuth application

1. Linear → **Settings** → **Account** → **API** → **OAuth applications**  
   Or: [linear.app/settings/api](https://linear.app/settings/api) → **Create new OAuth application**
2. **Name:** `MultiWorkAgent (local)`
3. **Redirect URI:** `http://127.0.0.1:5000/integrations/oauth/callback`
4. **Scopes:** enable **read** and **write** (matches registry: `read write`)
5. Create → copy **Client ID** and **Client secret**

## 2. Server env

```env
LINEAR_OAUTH_CLIENT_ID=
LINEAR_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 3. Test

1. One **business** selected  
2. **Data & integrations** → **Linear** → **OAuth**  
3. Approve in Linear → back to app

## 4. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | URI must match Linear app settings exactly |
| wrong workspace | OAuth is tied to the Linear org you authorize |

Doc: [Linear OAuth 2.0 authentication](https://developers.linear.app/docs/oauth/authentication)

## Next

**#11 Asana** — `ASANA_OAUTH_*`
