# OAuth walkthrough #18 — Zoom

Status: **done**

Registry scopes: `user:read meeting:read`

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Add `http://127.0.0.1:5000/integrations/oauth/callback` for local Flask if needed.

## 1. Create a Zoom app

1. [Zoom App Marketplace](https://marketplace.zoom.us/) → **Develop** → **Build General App** (OAuth app — not Server-to-Server unless you change approach)
2. **App name:** `MultiWorkAgent`
3. Choose **User-managed app** (OAuth) if prompted
4. **App credentials** tab → note type (Development vs Production)

## 2. OAuth & redirect

1. **OAuth** / **Redirect URL for OAuth** → add:
   ```text
   https://multiworkagent.vercel.app/integrations/oauth/callback
   ```
2. **Scopes** → add **user:read** and **meeting:read** (or equivalent user/meeting read scopes shown in the UI)
3. **Activation** — complete required fields (company name, developer contact, privacy policy URL):
   ```text
   https://multiworkagent.vercel.app/privacy-policy
   ```

## 3. Credentials

On **App credentials** (Development for testing, Production when live):

- **Client ID** → `ZOOM_OAUTH_CLIENT_ID`
- **Client Secret** → `ZOOM_OAUTH_CLIENT_SECRET`

Development credentials work with Zoom test users; switch to Production credentials and activate the app for real accounts.

## 4. Local `.env`

```env
ZOOM_OAUTH_CLIENT_ID=
ZOOM_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 5. Test

1. Open app at URL matching registered redirect (`APP_BASE_URL`)
2. One **business** selected
3. **Data & integrations** → **Zoom** → **OAuth**
4. Sign in to Zoom and **Allow**

## 6. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | Redirect URL in Zoom app must match exactly |
| invalid scope | Add user:read and meeting:read on the app |
| App not activated | Finish Zoom app activation checklist |
| Dev vs prod | Use Development client with dev/test users first |

Doc: [Zoom OAuth](https://developers.zoom.us/docs/integrations/oauth/)

## Next

**#19 Airtable** — [19-airtable.md](19-airtable.md)
