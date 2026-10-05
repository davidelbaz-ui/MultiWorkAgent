# Operator admin console

Separate Flask app for local operations. **Not deployed to Vercel.**

## Run

1. Postgres running and `DATABASE_URL` in `.env` (same as main app).
2. Set in `.env`:

```env
ADMIN_EMAIL=you@example.com
ADMIN_PASSWORD=your-local-password
ADMIN_PORT=8000
ADMIN_HOST=127.0.0.1
```

3. Main app (customers): `python app.py` → http://127.0.0.1:5000  
4. Admin console: `python admin_app.py` → **http://127.0.0.1:8000**

## Features

| Area | URL | Purpose |
|------|-----|---------|
| Dashboard | `/` | Counts, DB schema version, open support |
| Contact support | `/support` | Inbox, reply, open/close threads |
| Page settings | `/pages` | Start page copy, maintenance mode |
| Logs | `/logs` | In-memory log buffer (this process) |
| System & DB | `/system` | Connection diagnostics, env key status |

Uses the same PostgreSQL database as the main app.
