# OAuth walkthrough #8 — Confluence (Atlassian)

Status: **done**

Uses the **same** `.env` as Jira:

```env
ATLASSIAN_OAUTH_CLIENT_ID=
ATLASSIAN_OAUTH_CLIENT_SECRET=
```

Callback is unchanged: `http://127.0.0.1:5000/integrations/oauth/callback`

## 1. Atlassian app (if not already done for Jira)

In [Developer console](https://developer.atlassian.com/console/myapps/) → your **OAuth 2.0 integration**:

1. **Authorization** → callback URL already set.
2. **Permissions** → enable **Confluence** scopes, e.g.:
   - `read:confluence-content.all`
   - `write:confluence-content` (optional)
   - `offline_access`

If those scopes were not enabled when you built the Jira app, add them and **Save** (users may need to reconnect).

## 2. Test in MultiWorkAgent

1. One **business** selected  
2. **Data & integrations** → **Confluence** → **OAuth**  
3. Choose site → **Accept**

This creates a **separate** business connection from Jira (different `provider_slug`), even though the Atlassian client ID is shared.

## 3. “Add” spins and returns to Add (Confluence API)

This is a **Developer Console UI** issue. Try in order:

1. **Hard refresh** or **InPrivate/Incognito** (disable ad blockers for `developer.atlassian.com`).
2. After **Add**, click **Configure** on the Confluence row (if it appears) and enable scopes there — some tenants never flip the button to “Configure” until a second try.
3. Confirm you have **Confluence Cloud** on the site (Jira-only sites may not attach Confluence API).
4. **Workaround:** create a **new** OAuth 2.0 integration and add **both** Jira API and Confluence API during setup, then move `ATLASSIAN_OAUTH_*` to the new Client ID/Secret.
5. **Skip console for a test:** in MultiWorkAgent → **Confluence** → **OAuth** anyway. If consent lists Confluence, you’re fine; if it errors on scopes, the console step is still required.

## 4. Common issues (connect)

| Issue | Fix |
|-------|-----|
| Consent shows no Confluence | Add Confluence scopes on the Atlassian app (or use workaround above) |
| Same site as Jira | Normal — one site can host both products |

## Next

**#9 Notion** — `NOTION_OAUTH_*` (`09-notion.md`)
