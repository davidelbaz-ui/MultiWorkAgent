# OAuth walkthrough #4 — Google Workspace (integrations)

Status: **done**

Uses **`GOOGLE_OAUTH_*`** — **not** `GOOGLE_LOGIN_*` (sign-in uses a different OAuth client and callback).

## Callback URL (integrations)

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

Sign-in callback stays: `http://127.0.0.1:5000/auth/google/callback`

## 1. Google Cloud Console

1. [Google Cloud Console](https://console.cloud.google.com/) — same or new project as login.
2. **APIs & Services** → **OAuth consent screen**
   - Add scopes your app will request (or add when prompted during test):
     - Gmail API: `.../auth/gmail.readonly`
     - Drive: `.../auth/drive.readonly`
     - Sheets: `.../auth/spreadsheets.readonly`
     - Calendar: `.../auth/calendar.readonly`
   - Add yourself as a **test user** if app is in **Testing**.
3. **Credentials** → **Create credentials** → **OAuth client ID** → **Web application**
4. Name: e.g. `MultiWorkAgent Integrations (local)`
5. **Authorized redirect URIs** — add **only**:

   ```text
   http://127.0.0.1:5000/integrations/oauth/callback
   ```

6. Copy **Client ID** and **Client secret**

## 2. Enable APIs (recommended)

In **APIs & Services** → **Library**, enable for the project:

- Gmail API  
- Google Drive API  
- Google Sheets API  
- Google Calendar API  

## 3. Server env

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 4. Test in app

1. One **business** selected  
2. **Data & integrations** → **Google Workspace (Gmail, Docs, Drive, Sheets, Calendar)** → **OAuth**

## 5. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri_mismatch | Redirect must be `/integrations/oauth/callback`, not `/auth/google/callback` |
| access blocked / app not verified | Testing mode: add your Google account as test user on consent screen |
| insufficient scopes | Add API scopes on consent screen + enable APIs |

## Next

**#5 Microsoft 365** (`05-microsoft-365.md`) — `MICROSOFT_OAUTH_*`

## Deferred

**#3 Bitbucket** — retry when workspace slug / UI is sorted (`03-bitbucket.md`)
