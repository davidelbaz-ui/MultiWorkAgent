# Operator admin console

Production and local: **`https://your-domain/admin`** (e.g. [multiworkagent.vercel.app/admin](https://multiworkagent.vercel.app/admin)).

Separate from customer **Sign in** — uses operator credentials only.

## Configure

Set in **Vercel → Production env** (and local `.env`):

```env
ADMIN_EMAIL=operator@yourdomain.com
ADMIN_PASSWORD=use-a-long-random-password
```

Optional: `ADMIN_PASSWORD_HASH` (werkzeug) instead of plain `ADMIN_PASSWORD`.

Redeploy after changing env vars on Vercel.

## Sections

| Path | Purpose |
|------|---------|
| `/admin` | Operator sign-in |
| `/admin/` | Dashboard |
| `/admin/support` | Contact support inbox |
| `/admin/pages` | Start page copy, maintenance mode |
| `/admin/logs` | In-memory log buffer (this server process) |
| `/admin/system` | DB status, table counts |

## Local dev

```bash
python app.py          # http://127.0.0.1:5000/admin
# or
python admin_app.py    # http://127.0.0.1:8000/admin (same app, different port)
```

Customer app and admin share one database and one deployment on Vercel.
