# OAuth walkthrough #21 — Vercel

Status: **wired** (Vercel **Marketplace integration** flow, not Sign in with Vercel).

Callback:

```text
https://multiworkagent.vercel.app/integrations/oauth/callback
```

## 1. Create a Vercel Integration

1. Vercel dashboard → **Integrations** → **Create Integration** (or [Integrations Console](https://vercel.com/dashboard/integrations/console)).
2. Set **Redirect URL** to your callback URL above.
3. Choose the API scopes your agent needs (start with read-only deployment/project scopes).
4. Save → copy **Client ID**, **Client secret**, and the integration **slug** (URL segment under `vercel.com/integrations/{slug}/`).

Doc: [Building Integrations with Vercel REST API](https://vercel.com/docs/integrations/create-integration/vercel-api-integrations)

## 2. Server env

```env
VERCEL_OAUTH_CLIENT_ID=
VERCEL_OAUTH_CLIENT_SECRET=
VERCEL_OAUTH_INTEGRATION_SLUG=your-integration-slug
```

Restart the app. OAuth is only “configured” when all three are set.

## 3. Test

1. Pick **one business** in the header.
2. **Data & integrations** → **Vercel** → **OAuth** → approve install.

Token exchange uses `POST https://api.vercel.com/v2/oauth/access_token`.

## Next

**#22 Render** — no public OAuth app for third parties; use **API key** in the connect UI until Render OAuth is added.
