# OAuth walkthrough #11 — Asana

Status: **your turn**

Registry scopes: `default` (full app permissions as configured in the Asana app).

## Callback URL

Asana’s docs require **HTTPS** for web redirect URLs (not `http://127.0.0.1`).

**Option A — production domain (recommended)**

On Vercel (**multiworkagent.vercel.app**):

1. Register redirect URI:

   ```text
   https://multiworkagent.vercel.app/integrations/oauth/callback
   ```

2. In Vercel env: `APP_BASE_URL=https://multiworkagent.vercel.app` (see [VERCEL.md](../../VERCEL.md))
3. Open **https://multiworkagent.vercel.app** → **Data & integrations** → **Asana** → **OAuth**

**Option B — local tunnel**

1. Run a tunnel to port 5000, e.g. `ngrok http 5000`
2. Register `https://YOUR-NGROK-HOST/integrations/oauth/callback` and set `APP_BASE_URL` to that host
3. Open MultiWorkAgent via the **same HTTPS URL** when testing OAuth

**Option C — skip OAuth for now:** **Data & integrations** → **Asana** → **API key** (Personal Access Token).

## 1. Create app

1. [app.asana.com/0/my-apps](https://app.asana.com/0/my-apps) → **Create new app**
2. Name: `MultiWorkAgent (local)` → pick a use case → **Create app**

## 2. OAuth + distribution

1. Left menu → **OAuth** → **Add redirect URL** → your **HTTPS** callback (above) → **Add**
2. **Test & distribute** → **Manage distribution** → **Any workspace** (or your workspace) → **Save**
3. **Basic information** (or OAuth page) → copy **Client ID** and **Client secret**

## 3. Server env

```env
ASANA_OAUTH_CLIENT_ID=
ASANA_OAUTH_CLIENT_SECRET=
```

Restart Flask (with `APP_BASE_URL` matching the registered redirect host).

## 4. Test

1. One **business** selected  
2. Open app at **`APP_BASE_URL`** (HTTPS if using ngrok)  
3. **Data & integrations** → **Asana** → **OAuth**

## 5. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri must be https | Use ngrok (or similar) and update Asana + `APP_BASE_URL` |
| App not available in workspace | **Manage distribution** → allow your workspace |
| Token error | Redirect URI must match exactly; restore `APP_BASE_URL` after testing if you changed it |

Doc: [Asana OAuth](https://developers.asana.com/docs/oauth)

## Next

**#12 Discord** — `DISCORD_OAUTH_*`
