# OAuth walkthrough #9 — Notion

Status: **done**

## Callback URL

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

## 1. Create an OAuth connection (Developer tools)

1. Working entry points (same account):
   - [https://www.notion.com/profile/integrations](https://www.notion.com/profile/integrations)
   - [https://app.notion.com/developers/connections](https://app.notion.com/developers/connections) → **New connection**  
   If `notion.so` is blank, use **notion.com** / **app.notion.com** — not a different product.
2. **Connection name:** e.g. `MultiWorkAgent`
3. **Authentication method:** **OAuth** (not API token)
4. **Development workspace:** pick a workspace (required on the full form — scroll if you don’t see it)
5. **Redirect URIs:** Notion **does not allow IP addresses** (no `127.0.0.1`). Use:

   ```text
   http://localhost:5000/integrations/oauth/callback
   ```

   Type the URL and press **Enter** so it becomes a chip.

   When connecting Notion in MultiWorkAgent, open the app at **`http://localhost:5000`** (same host as the redirect). Other integrations can keep using `127.0.0.1` if that’s what you registered elsewhere.

6. **Capabilities:** enable at least **Read content** (scroll down on the form if **Create connection** stays grey)
7. **Create connection** → **Configuration** tab for OAuth client ID/secret

## 2. Credentials

Copy **OAuth client ID** and **OAuth client secret** (not the internal integration secret unless that’s what Notion labels for public OAuth — use the OAuth pair from the public integration settings).

## 3. Server env

```env
NOTION_OAUTH_CLIENT_ID=
NOTION_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 4. Test

1. One **business** selected  
2. **Data & integrations** → **Notion** → **OAuth**  
3. Pick workspace → **Select pages** (Notion asks which pages the integration can access) → allow

## 5. Common issues

| Issue | Fix |
|-------|-----|
| Integration must be public | Internal integrations use API tokens, not this OAuth flow |
| redirect_uri mismatch | Redirect URI must match exactly in Notion integration settings |
| No pages visible | User must grant page access during OAuth |

Doc: [Notion Authorization](https://developers.notion.com/docs/authorization)

## Next

**#10 Linear** — `LINEAR_OAUTH_*`
