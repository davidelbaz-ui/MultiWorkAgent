# Operator admin console

Production and local: **`https://your-domain/admin`** (e.g. [multiworkagent.vercel.app/admin](https://multiworkagent.vercel.app/admin)).

Separate from customer **Sign in** — uses operator credentials only.

## Configure

Set in **Vercel → Project → Settings → Environment Variables** for **Production** (and local `.env` for `python app.py` only — **`.env` is not uploaded to Vercel**):

```env
ADMIN_EMAIL=operator@yourdomain.com
ADMIN_PASSWORD=use-a-long-random-password
```

Optional: `ADMIN_PASSWORD_HASH` (werkzeug) instead of plain `ADMIN_PASSWORD`.

After adding or changing variables on Vercel, click **Redeploy** (existing deployments keep old env until redeploy).

**Verify on production:** `GET https://your-domain/admin/ping` should return `{"ok":true,"admin":true,"db":true}`. If `"admin":false`, `ADMIN_EMAIL` / `ADMIN_PASSWORD` are missing or invalid in that deployment’s env.

## Sections

| Path | Purpose |
|------|---------|
| `/admin` | Operator sign-in |
| `/admin/` | Dashboard |
| `/admin/users` | Customer accounts (name, email, created, last login) |
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
