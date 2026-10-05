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
| **`DATABASE_URL`** | `postgresql://user:password@host:5432/dbname` (Vercel Postgres, Neon, Supabase, etc.) |
| `GOOGLE_LOGIN_CLIENT_ID` / `SECRET` | login OAuth (redirect below) |
| `INTEGRATION_ENCRYPTION_KEY` | optional but recommended |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | operator console at **`/admin`** (see [docs/ADMIN.md](docs/ADMIN.md)) |

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

Agent, Square billing, database drivers: set the same vars you use locally (`AGENT_API_KEY`, `SQUARE_*`, etc.). Full Square subscription setup: [docs/SQUARE_BILLING.md](docs/SQUARE_BILLING.md).

## OAuth on HTTPS (Asana, etc.)

With `APP_BASE_URL=https://multiworkagent.vercel.app`, integration OAuth uses HTTPS — no ngrok required when testing against the deployed app.

## Local dev vs production

| | `APP_BASE_URL` | Where you connect OAuth |
|--|----------------|-------------------------|
| Local Flask | `http://127.0.0.1:5000` | Register **local** callbacks in each provider *or* test only on Vercel |
| Vercel | `https://multiworkagent.vercel.app` | Register **Vercel** callbacks once; use the live site for Connect |

Operator rule: for the walkthrough, register **`https://multiworkagent.vercel.app/integrations/oauth/callback`** (and login URLs above) in each provider app unless you intentionally maintain separate local OAuth clients.

## Database (PostgreSQL)

All app data (accounts, businesses, chats, support, billing) lives in **PostgreSQL** via **`DATABASE_URL`**. The username and password are part of the URL — there is no separate SQLite file on Vercel.

**Local:** `docker compose up -d` then set in `.env`:

```text
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent
```

**Vercel:** create [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres), then **Connect Project** and choose **MultiWorkAgent** so `POSTGRES_URL` is injected for **Production**. **Delete** any manual `DATABASE_URL` you pasted from local `.env` (especially `127.0.0.1`). **Redeploy** and open `/health` — `database_env.env_keys.POSTGRES_URL` should be `remote`, not `missing`.

Do **not** copy your Docker `DATABASE_URL` into Vercel unless the host is a remote provider (Neon, Supabase, etc.).

See [docs/DATABASE.md](docs/DATABASE.md).

Chat **file uploads** still use `/tmp` on Vercel until object storage is added.

Also set **`FLASK_SECRET_KEY`** to a stable random value (changing it logs everyone out).

## Local vs production commands

- **Local:** Postgres running, `DATABASE_URL` in `.env`, `APP_BASE_URL=http://127.0.0.1:5000`, `python app.py`
- **Production:** env in Vercel; redeploy after changing env vars
