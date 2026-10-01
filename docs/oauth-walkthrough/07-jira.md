# OAuth walkthrough #7 — Jira (Atlassian)

Status: **done**

One Atlassian **OAuth 2.0 (3LO)** app powers both **Jira** and **Confluence** (`ATLASSIAN_OAUTH_*`).

## Callback URL

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

## 1. Create OAuth 2.0 integration

1. [developer.atlassian.com](https://developer.atlassian.com/) → profile (top right) → **Developer console**
2. **Create** → **OAuth 2.0 integration**
3. **Name:** `MultiWorkAgent (local)`

## 2. Authorization (3LO)

1. Open your app → **Authorization** (left)
2. **OAuth 2.0 (3LO)** → **Configure**
3. **Callback URL:**  
   `http://127.0.0.1:5000/integrations/oauth/callback`  
   **Save**

## 3. Permissions (Jira scopes)

In the developer console, add **Jira** API scopes that match the app (wording varies by console version), including:

- `read:jira-work`
- `write:jira-work` (optional for read-only testing)
- `read:jira-user`
- `offline_access` (refresh token)

Our registry sends these scopes on authorize. Enable equivalent permissions in the console if it asks for granular toggles.

## 4. Credentials

**Settings** (or app overview) → copy **Client ID** and **Secret**.

## 5. Server env

```env
ATLASSIAN_OAUTH_CLIENT_ID=
ATLASSIAN_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 6. Test

1. One **business** selected  
2. **Data & integrations** → **Jira** → **OAuth**  
3. Pick your **Atlassian cloud site** when prompted → **Accept**

## 7. Confluence later

Same env vars → connect **Confluence** tile (different scopes, same Atlassian app).

## 8. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | Callback in Authorization must match exactly |
| Token exchange failed | App uses JSON token exchange (fixed in `integration_oauth.py` for Atlassian) |
| No accessible resources | Grant app access to the Jira site during consent |

Doc: [OAuth 2.0 (3LO) apps — Jira](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)

## Next

**#8 Confluence** — same `ATLASSIAN_OAUTH_*`, connect Confluence tile. Then **#9 Notion**.
