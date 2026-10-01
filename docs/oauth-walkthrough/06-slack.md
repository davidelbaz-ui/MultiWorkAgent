# OAuth walkthrough #6 — Slack

Status: **done**

## Callback URL

```text
http://127.0.0.1:5000/integrations/oauth/callback
```

## 1. Create a Slack app

1. [Slack API → Your Apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. **App name:** `MultiWorkAgent (local)`
3. **Workspace:** pick the workspace where you want to test

## 2. OAuth & Permissions

1. Left menu → **OAuth & Permissions**
2. **Redirect URLs** → **Add New Redirect URL** →  
   `http://127.0.0.1:5000/integrations/oauth/callback` → **Save URLs**
3. **Scopes** → **User Token Scopes** (registry uses user OAuth v2):
   - `channels:read`
   - `chat:write`
   - `users:read`  
   Add more later if the agent needs them.

## 3. Credentials

1. **Basic Information** → **App Credentials**
2. Copy **Client ID** and **Client Secret** (Signing Secret is for events, not OAuth start)

## 4. Install to workspace (optional before test)

**Install to Workspace** on the OAuth page can pre-install; MultiWorkAgent will also send users through OAuth on connect.

## 5. Server env

```env
SLACK_OAUTH_CLIENT_ID=
SLACK_OAUTH_CLIENT_SECRET=
```

Restart Flask.

## 6. Test

1. One **business** selected  
2. **Data & integrations** → **Slack** → **OAuth**  
3. Allow access in Slack → return to app

## 7. Common issues

| Issue | Fix |
|-------|-----|
| redirect_uri did not match | Redirect URL in Slack app must match exactly |
| invalid_scope | Add scopes under **User Token Scopes** |
| wrong workspace | Reinstall / reconnect and pick the intended workspace |

## Next

**#7 Jira** — same `ATLASSIAN_OAUTH_*` as Confluence if you already created an Atlassian developer app; otherwise new Atlassian OAuth (`07-jira.md`).
