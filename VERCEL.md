# Deploy MultiWorkAgent on Vercel

Production URL: **https://multiworkagent.com** (custom domain).  
Fallback: `https://multiworkagent.vercel.app`

Set **`APP_BASE_URL=https://multiworkagent.com`** in Vercel (no trailing slash). All login, integration, and Square webhook URLs are derived from it.

**Go-live checklist (Claude + Square):** [docs/PRODUCTION_GO_LIVE.md](docs/PRODUCTION_GO_LIVE.md)

## Import

1. Push this repo to GitHub (see README).
2. [Vercel](https://vercel.com/new) → Import **MultiWorkAgent** → Framework preset: **Flask** (auto-detects `app.py`).
3. Attach **multiworkagent.com** in Project → Settings → Domains.
4. Add environment variables below for **Production** (and Preview only if you use a different `APP_BASE_URL` there).

## Deploy updates from GitHub

Vercel **automatically builds** when you push to `main`. After changing **Environment Variables**, click **Redeploy**.

## Required environment variables (production)

| Variable | Value |
|----------|--------|
| `APP_ENV` | `production` |
| `FLASK_SECRET_KEY` | long random string |
| `APP_BASE_URL` | `https://multiworkagent.com` |
| **`DATABASE_URL`** | `postgresql://user:password@host:5432/dbname` (Vercel Postgres, Neon, Supabase, etc.) |
| `GOOGLE_LOGIN_CLIENT_ID` / `SECRET` | login OAuth (redirect below) |
| `INTEGRATION_ENCRYPTION_KEY` | optional but recommended |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | operator console at **`/admin`** (see [docs/ADMIN.md](docs/ADMIN.md)) |

Login (see [AUTH_LOGIN.md](AUTH_LOGIN.md)):

| Variable | Callback to register |
|----------|----------------------|
| `GOOGLE_LOGIN_CLIENT_ID` / `SECRET` | `https://multiworkagent.com/auth/google/callback` |
| `MICROSOFT_LOGIN_CLIENT_ID` / `SECRET` | `https://multiworkagent.com/auth/microsoft/callback` |

Integration OAuth (every provider):

```text
https://multiworkagent.com/integrations/oauth/callback
```

Copy operator keys from `env.example` / [INTEGRATIONS_OAUTH.md](INTEGRATIONS_OAUTH.md) into Vercel env (never commit `.env`).

**Agent (pick one provider):**

| Provider | Variables |
|----------|-----------|
| Gemini (default) | `GEMINI_API_KEY`, optional `AGENT_MODEL` |
| Claude | `AGENT_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, optional `AGENT_MODEL` — see [docs/AGENT_CLAUDE.md](docs/AGENT_CLAUDE.md) |

Square billing: [docs/SQUARE_BILLING.md](docs/SQUARE_BILLING.md) and [docs/PRODUCTION_GO_LIVE.md](docs/PRODUCTION_GO_LIVE.md).

## Verify

- `https://multiworkagent.com/health` — `deployment.agent.ready`, `deployment.billing.mode`
- Admin → **System** — same flags without secrets

## OAuth on HTTPS

With `APP_BASE_URL=https://multiworkagent.com`, integration OAuth uses HTTPS — no ngrok required when testing the deployed app.

## Local dev vs production

| | `APP_BASE_URL` | Where you connect OAuth |
|--|----------------|-------------------------|
| Local Flask | `http://127.0.0.1:5000` | Register **local** callbacks in each provider *or* test only on Vercel |
| Vercel | `https://multiworkagent.com` | Register **production** callbacks once |

## Database (PostgreSQL)

All app data lives in **PostgreSQL** via **`DATABASE_URL`**.

**Local:** `docker compose up -d` then:

```text
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent
```

**Vercel:** connect [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres) to the project. **Redeploy** and open `/health`.

See [docs/DATABASE.md](docs/DATABASE.md).

Also set **`FLASK_SECRET_KEY`** to a stable random value (changing it logs everyone out).
