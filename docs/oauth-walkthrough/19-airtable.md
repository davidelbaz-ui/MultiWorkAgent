# OAuth walkthrough #19 — Airtable

Status: **done**

Registry scopes: `data.records:read data.records:write schema.bases:read`

## Callback URL

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

Add `http://127.0.0.1:5000/integrations/oauth/callback` for local Flask if needed.

## 1. Register an OAuth integration

1. [Airtable Builder Hub](https://airtable.com/developers/web/guides/oauth-integrations) or **Airtable** → account → **Developer hub** / **Create OAuth integration**
2. Direct: [airtable.com/create/oauth](https://airtable.com/create/oauth) (if available while signed in)
3. **Integration name:** `MultiWorkAgent`
4. **Redirect URL:** callback above (+ local if needed)
5. **Scopes:** enable **data.records:read**, **data.records:write**, **schema.bases:read** (match registry)

## 2. Credentials

After creating the integration:

- **Client ID** → `AIRTABLE_OAUTH_CLIENT_ID`
- **Client secret** → `AIRTABLE_OAUTH_CLIENT_SECRET`

## 3. Local `.env`

```env
AIRTABLE_OAUTH_CLIENT_ID=
AIRTABLE_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 4. Test

1. Open app at URL matching registered redirect (`APP_BASE_URL`)
2. One **business** selected
3. **Data & integrations** → **Airtable** → **OAuth**
4. Authorize access to your Airtable account / bases

## 5. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri mismatch | Redirect URL must match `{APP_BASE_URL}/integrations/oauth/callback` exactly |
| invalid_scope | Add all three scopes on the Airtable integration |
| OAuth not enabled | Both `AIRTABLE_OAUTH_*` set and Flask restarted |

Doc: [Airtable OAuth integrations](https://airtable.com/developers/web/guides/oauth-integrations)

## Next

All **wired** OAuth providers in `integration_oauth_registry.py` are done (except **Bitbucket**, deferred). Remaining catalog slugs need URLs added to the registry before Connect → OAuth works—use **API key** until then.
