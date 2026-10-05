# Sign in with Google

MultiWorkAgent uses **server-side OAuth 2.0 / OpenID Connect** with Flask sessions (not Firebase Auth). Configure credentials in **Google Cloud**.

Use a **separate OAuth client** from integration OAuth (`GOOGLE_OAUTH_*` / business connections). The login client only needs identity scopes.

## Environment variables

```env
GOOGLE_LOGIN_CLIENT_ID=
GOOGLE_LOGIN_CLIENT_SECRET=
```

Set **`APP_BASE_URL`** to your public site URL (see redirect URIs below).

## Redirect URIs (required)

Register these **exact** callback URLs in Google Cloud (must match `APP_BASE_URL`):

| Environment | Callback URL |
|-------------|--------------|
| Production (Vercel) | `https://multiworkagent.vercel.app/auth/google/callback` |
| Local dev | `http://127.0.0.1:5000/auth/google/callback` |

Microsoft login uses the same host: `https://multiworkagent.vercel.app/auth/microsoft/callback`.

Set **`APP_BASE_URL=https://multiworkagent.vercel.app`** on Vercel (Production). Also set **`FLASK_SECRET_KEY`** to a stable random value (OAuth state is signed with it). If `APP_BASE_URL` is missing on Vercel, the app defaults to `https://multiworkagent.vercel.app` when `VERCEL` is set—you must still register that callback in Google Cloud.

## Google Cloud

1. [Google Cloud Console](https://console.cloud.google.com/) → create or select a project.
2. **APIs & Services** → **OAuth consent screen** → External (or Internal for Workspace-only) → scopes `email`, `profile`, `openid`.
3. **Credentials** → **Create credentials** → **OAuth client ID** → **Web application**.
4. Add authorized redirect URIs from the table above.
5. Copy **Client ID** and **Client secret** → `GOOGLE_LOGIN_CLIENT_ID` / `GOOGLE_LOGIN_CLIENT_SECRET`.

### Optional: Firebase project (credentials only)

This app does **not** use the Firebase Web SDK. You can enable **Google** in [Firebase Console](https://console.firebase.google.com/) → **Authentication**, then in the linked Google Cloud project open the **Web client** credentials, add the Flask redirect URIs above, and copy ID/secret into `.env`.

Restart Flask after updating `.env`. The Google button works when both ID and secret are set.

## Behavior

- **New user**: creates account + owner membership + linked Google identity.
- **Returning user**: signs in via Google `sub`.
- **Same email as existing password account**: links Google identity and signs in (Google email must be verified).

Email/password sign-in remains available.

## Routes

- `GET /auth/google/start` (optional `?next=/path`)
- `GET /auth/google/callback`
