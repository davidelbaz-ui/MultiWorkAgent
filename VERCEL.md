# Deploy MultiWorkAgent on Vercel

Production URL for OAuth redirects: **https://multiworkagent.vercel.app**

Set **`APP_BASE_URL`** to that exact value in Vercel (no trailing slash). All login and integration callbacks are derived from it.

## Import

1. Push this repo to GitHub (see README).
2. [Vercel](https://vercel.com/new) → Import **MultiWorkAgent** → Framework preset: **Flask** (auto-detects `app.py`).
3. Confirm the project’s **`.vercel.app`** domain is `multiworkagent.vercel.app` (Vercel → Project → Settings → Domains).
4. Add environment variables below for **Production** (and Preview only if you use a different `APP_BASE_URL` there).

## Deploy updates from GitHub

Vercel **automatically builds** when you push to `main`. You do **not** pull on the server. After changing **Environment Variables**, click **Redeploy** (env changes are not applied to old deployments until redeploy).

## Required environment variables (production)

| Variable | Value |
|----------|--------|
| `APP_ENV` | `production` |
| `FLASK_SECRET_KEY` | long random string |
| `APP_BASE_URL` | `https://multiworkagent.vercel.app` |
| `GOOGLE_LOGIN_CLIENT_ID` / `SECRET` | login OAuth (redirect below) |
| `INTEGRATION_ENCRYPTION_KEY` | optional but recommended |

Login (see [AUTH_LOGIN.md](AUTH_LOGIN.md)):

| Variable | Callback to register |
|----------|----------------------|
| `GOOGLE_LOGIN_CLIENT_ID` / `SECRET` | `https://multiworkagent.vercel.app/auth/google/callback` |
| `MICROSOFT_LOGIN_CLIENT_ID` / `SECRET` | `https://multiworkagent.vercel.app/auth/microsoft/callback` |

Integration OAuth (every provider):

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Copy operator keys from `.env.example` / [INTEGRATIONS_OAUTH.md](INTEGRATIONS_OAUTH.md) into Vercel env (never commit `.env`).

Agent, Square billing, database drivers: set the same vars you use locally (`AGENT_API_KEY`, `SQUARE_*`, etc.).

## OAuth on HTTPS (Asana, etc.)

With `APP_BASE_URL=https://multiworkagent.vercel.app`, integration OAuth uses HTTPS — no ngrok required when testing against the deployed app.

## Local dev vs production

| | `APP_BASE_URL` | Where you connect OAuth |
|--|----------------|-------------------------|
| Local Flask | `http://127.0.0.1:5000` | Register **local** callbacks in each provider *or* test only on Vercel |
| Vercel | `https://multiworkagent.vercel.app` | Register **Vercel** callbacks once; use the live site for Connect |

Operator rule: for the walkthrough, register **`https://multiworkagent.vercel.app/integrations/oauth/callback`** (and login URLs above) in each provider app unless you intentionally maintain separate local OAuth clients.

## Storage and login on Vercel

Without a remote database, SQLite under **`/tmp`** is **ephemeral** (each serverless instance has its own empty file). The app **keeps you signed in via the session cookie** between page loads, but businesses, chats, and OAuth-linked accounts do not persist across instances until you add Turso.

**Recommended:** create a [Turso](https://turso.tech) database and set on Vercel (Production):

| Variable | Value |
|----------|--------|
| `TURSO_DATABASE_URL` | `libsql://…` from Turso dashboard |
| `TURSO_AUTH_TOKEN` | Turso database token |

All app, agent chat, and support tables use that single remote database automatically.

Also set **`FLASK_SECRET_KEY`** to a stable random value (never change it casually — changing it logs everyone out).

Chat file uploads still use local `/tmp` until object storage is added.

## Local vs production commands

- **Local:** `APP_BASE_URL=http://127.0.0.1:5000`, `python app.py`
- **Production:** env in Vercel; redeploy after changing env vars
