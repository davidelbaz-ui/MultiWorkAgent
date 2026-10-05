# OAuth walkthrough #20 — Netlify

Status: **wired** in `integration_oauth_registry.py`.

Callback (same as all integrations):

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Add `http://127.0.0.1:5000/integrations/oauth/callback` if you test locally with that `APP_BASE_URL`.

## 1. Register an OAuth application

1. Log in at [app.netlify.com](https://app.netlify.com).
2. **User settings** (avatar) → **Applications** → **OAuth applications** → **New OAuth application**.
3. **Name:** `MultiWorkAgent`
4. **Redirect URI:** your callback URL above (exact match).
5. Save → copy **Client ID** and **Client secret**.

## 2. Server env

```env
NETLIFY_OAUTH_CLIENT_ID=
NETLIFY_OAUTH_CLIENT_SECRET=
```

Restart the app.

## 3. Test

1. Pick **one business** in the header.
2. **Data & integrations** → **Netlify** → **OAuth**.

## Next

**#21 Vercel** — [21-vercel.md](21-vercel.md)
