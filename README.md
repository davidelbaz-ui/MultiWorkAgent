# MultiWorkAgent

Multi-tenant business operations agent: businesses, integrations, databases, agent runs, billing, and usage metering.

Production site: **https://multiworkagent.vercel.app** (Vercel).

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy env.example .env    # edit secrets
python app.py
```

Open http://127.0.0.1:5000

Operator admin (support inbox, page copy, logs, DB status): `python admin_app.py` → http://127.0.0.1:8000 — see [docs/ADMIN.md](docs/ADMIN.md).

## Deploy on Vercel

See [VERCEL.md](VERCEL.md). Set `APP_BASE_URL=https://multiworkagent.vercel.app` in production.

## OAuth login

See [AUTH_LOGIN.md](AUTH_LOGIN.md).

## Integrations OAuth

See [INTEGRATIONS_OAUTH.md](INTEGRATIONS_OAUTH.md) and [docs/oauth-walkthrough/](docs/oauth-walkthrough/).

## Tests

```bash
python -m pytest tests/ -q
```
