# OAuth walkthrough #1 — GitHub

Status: **done**

## Already done in code

- Registry entry wired in `integration_oauth_registry.py`
- Callback route: `/integrations/oauth/callback`

## 1. Create a GitHub OAuth App

1. GitHub → **Settings** → **Developer settings** → **OAuth Apps** → **New OAuth App**
2. **Application name:** `MultiWorkAgent (local)` (any label)
3. **Homepage URL:** `http://127.0.0.1:5000`
4. **Authorization callback URL** (must match exactly):

   ```text
   http://127.0.0.1:5000/integrations/oauth/callback
   ```

5. Register → copy **Client ID** → generate **Client secret**

## 2. Server env

In `.env`:

```env
GITHUB_OAUTH_CLIENT_ID=your_client_id
GITHUB_OAUTH_CLIENT_SECRET=your_client_secret
```

(`APP_BASE_URL` is already `http://127.0.0.1:5000`.)

## 3. Restart Flask

Stop and start `python app.py` so env loads.

## 4. Test in the app

1. Header → pick **one business** (not “All businesses”)
2. **Data & integrations** → **GitHub** → **OAuth**
3. Approve on GitHub → you should land back with “Integration connected successfully”

## 5. If it fails

| Symptom | Fix |
|--------|-----|
| “OAuth is not enabled on this server” | Empty `GITHUB_OAUTH_*` or app not restarted |
| Redirect URI mismatch | Callback URL in GitHub app must match `APP_BASE_URL` + `/integrations/oauth/callback` |
| Token exchange error | Secret typo; regenerate secret in GitHub |

## Next

When GitHub works, continue with **`02-gitlab.md`** (we’ll add that file when you’re ready).
