# PostgreSQL setup

MultiWorkAgent uses **PostgreSQL only** for application data. Configure a single connection string:

```text
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
```

Vercel also accepts **`POSTGRES_URL`** if `DATABASE_URL` is unset (same format).

On startup the app runs versioned migrations automatically (see `app_migrations.py`).

## Local development

1. Start Postgres:

   ```bash
   docker compose up -d
   ```

2. Copy from `.env.example` into `.env`:

   ```text
   DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent
   ```

3. Run the app: `python app.py`

## Vercel production

1. Add **Vercel Postgres** (or external Neon / Supabase) to the project.
2. Set **`DATABASE_URL`** to the provided connection string (includes password).
3. Redeploy after changing env vars.

Without `DATABASE_URL`, the app cannot save businesses, users, or chats.

## Tests

Tests require PostgreSQL. Default:

```text
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/multiworkagent_test
```

Create the database once:

```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE multiworkagent_test;"
```

Run: `python -m pytest`
