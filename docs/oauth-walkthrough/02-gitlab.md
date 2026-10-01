# OAuth walkthrough #2 — GitLab

Status: **done**

Uses **GitLab.com** (`gitlab.com` URLs in the registry). Self-hosted GitLab needs different authorize/token URLs later.

## 1. Create a GitLab application

1. Sign in at [gitlab.com](https://gitlab.com)
2. Avatar → **Preferences** → **Applications**  
   (Direct: `https://gitlab.com/-/user_settings/applications`)
3. **Add new application**
4. **Name:** `MultiWorkAgent (local)` (any label)
5. **Redirect URI** (exact):

   ```text
   http://127.0.0.1:5000/integrations/oauth/callback
   ```

6. **Confidential:** Yes (you get a client secret)
7. **Scopes:** enable at least **read_user**, **api** (matches registry: `read_user api read_api`)
8. Save → copy **Application ID** (Client ID) and **Secret**

## 2. Server env

In `.env`:

```env
GITLAB_OAUTH_CLIENT_ID=application_id_from_gitlab
GITLAB_OAUTH_CLIENT_SECRET=secret_from_gitlab
```

## 3. Restart Flask

Restart `python app.py` after saving `.env`.

## 4. Test

1. Header → one **business**
2. **Data & integrations** → **GitLab** → **OAuth**
3. Approve on GitLab → “Integration connected successfully”

## 5. If it fails

| Symptom | Fix |
|--------|-----|
| redirect_uri mismatch | Redirect URI in GitLab must match callback URL exactly |
| invalid_scope | Enable **api** and **read_user** on the GitLab app |
| Self-hosted GitLab | Registry points at gitlab.com; say if you need self-hosted URLs |

## Next

When GitLab works → **#3 Bitbucket** (`03-bitbucket.md`).
