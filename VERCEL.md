# Deploy MultiWorkAgent on Vercel

Custom domain: **https://multiworkagent.com** (set in Vercel → Project → Domains).

## Import

1. Push this repo to GitHub (see README).
2. [Vercel](https://vercel.com/new) → Import **MultiWorkAgent** → Framework preset: **Flask** (auto-detects `app.py`).
3. Add environment variables below for **Production** (and Preview if you want OAuth on preview URLs).

## Required environment variables (production)

| Variable | Example / notes |
|----------|-----------------|
| `APP_ENV` | `production` |
| `APP_BASE_URL` | `https://multiworkagent.com` |
| `FLASK_SECRET_KEY` | long random string |
| `INTEGRATION_ENCRYPTION_KEY` | optional but recommended |

Login (see [AUTH_LOGIN.md](AUTH_LOGIN.md)):

| Variable | Callback to register |
|----------|----------------------|
| `GOOGLE_LOGIN_CLIENT_ID` / `SECRET` | `https://multiworkagent.com/auth/google/callback` |
| `MICROSOFT_LOGIN_CLIENT_ID` / `SECRET` | `https://multiworkagent.com/auth/microsoft/callback` |

Integration OAuth (all providers): register

```text
https://multiworkagent.com/integrations/oauth/callback
```

Copy operator keys from `.env.example` / [INTEGRATIONS_OAUTH.md](INTEGRATIONS_OAUTH.md) into Vercel env (never commit `.env`).

Agent, Square billing, database drivers: set the same vars you use locally (`AGENT_API_KEY`, `SQUARE_*`, etc.).

## OAuth on HTTPS (Asana, etc.)

With `APP_BASE_URL=https://multiworkagent.com`, integration OAuth redirect URIs can use your domain — no ngrok required for providers that demand HTTPS.

## Storage caveat

On Vercel, SQLite and uploads live under **`/tmp/multiworkagent/storage`** (ephemeral). Data can reset on cold starts or redeploys. For durable production data, plan Postgres/Turso and object storage later.

## Local vs production

- **Local:** `APP_BASE_URL=http://127.0.0.1:5000`, `python app.py`
- **Production:** domain + env in Vercel; redeploy after changing env vars
