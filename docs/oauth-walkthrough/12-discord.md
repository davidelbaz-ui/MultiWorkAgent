# OAuth walkthrough #12 — Discord

Status: **done**

Registry scopes (sent on authorize): `identify guilds bot`

## Callback URL

Production (same as other integrations):

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

## 1. Create application

1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**
2. **Name:** `MultiWorkAgent`
3. **OAuth2** (left menu) → **Redirects** → **Add Redirect** → paste the callback URL above → **Save Changes**

## 2. Credentials

On **OAuth2** → **General**:

- Copy **Client ID**
- **Reset Secret** if needed → copy **Client Secret**

## 3. Scopes (for reference)

MultiWorkAgent requests `identify`, `guilds`, and `bot` when users click Connect. In the portal **OAuth2 URL Generator** you can tick the same scopes to preview the flow; you do not need a separate scope list in env vars.

If Discord shows a **bot install** screen, pick the server where the bot should be added. The `bot` scope is in the registry for future agent actions; adjust later if you prefer user-only OAuth.

## 4. Server env

**Vercel (Production)** — add or confirm:

```env
APP_BASE_URL=https://multiworkagent.vercel.app
DISCORD_OAUTH_CLIENT_ID=
DISCORD_OAUTH_CLIENT_SECRET=
```

Redeploy after changing env vars.

Local `.env` is only needed if you test against `127.0.0.1` with a separate redirect registered in Discord.

## 5. Test

1. Open **https://multiworkagent.vercel.app**
2. Select one **business**
3. **Data & integrations** → **Discord** → **OAuth**
4. Authorize in Discord → return to the app

## 6. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri OAuth2 error | Redirect in Discord must match `APP_BASE_URL` + `/integrations/oauth/callback` exactly |
| invalid client | Client ID/secret from **OAuth2**, not Bot token |
| OAuth not enabled on server | Set both `DISCORD_OAUTH_*` on Vercel and redeploy |

Doc: [Discord OAuth2](https://discord.com/developers/docs/topics/oauth2)

## Next

**#13 Salesforce** — [13-salesforce.md](13-salesforce.md)
