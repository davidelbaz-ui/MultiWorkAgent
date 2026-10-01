# OAuth walkthrough #3 — Bitbucket

Status: **deferred** (404 on workspace URL — revisit after the rest)

Bitbucket Cloud does **not** use “Personal settings” for OAuth anymore. Consumers live under a **workspace**.

## Path A — menus (recommended)

1. Go to [bitbucket.org](https://bitbucket.org) and log in.
2. Click your **avatar** (top right).
3. Under **Recent workspaces** or **All workspaces**, open the workspace that should own repos (often your **username** = personal workspace).
4. On that workspace’s pages, open the **gear (Settings)** in the **top** bar (not Atlassian account settings).
5. Choose **Workspace settings**.
6. Left sidebar: **Apps and features** → **OAuth consumers**.
7. **Add consumer**:
   - **Name:** `MultiWorkAgent (local)`
   - **Callback URL:** `http://127.0.0.1:5000/integrations/oauth/callback`
   - Check **This is a private consumer** (confidential / has a secret).
   - **Permissions:** Account **Read**, Repositories **Read** (minimum).
8. **Save** → expand the consumer → copy **Key** and **Secret**.

## Path B — direct URL

Replace `YOUR_WORKSPACE` with your workspace slug (often your Bitbucket username):

```text
https://bitbucket.org/YOUR_WORKSPACE/workspace/settings/oauth-consumers
```

New consumer:

```text
https://bitbucket.org/YOUR_WORKSPACE/workspace/settings/oauth-consumers/new
```

## If you don’t see “OAuth consumers”

- You must be in **Workspace settings** for a **Bitbucket workspace**, not [account.atlassian.com](https://account.atlassian.com) profile.
- On a **personal** workspace, only the **workspace owner** sees **Apps and features → OAuth consumers** (other admins may not).
- Use a **team workspace** you admin, or the personal workspace you own.

Official doc: [Use OAuth on Bitbucket Cloud](https://support.atlassian.com/bitbucket-cloud/docs/use-oauth-on-bitbucket-cloud/)

## Server env

```env
BITBUCKET_OAUTH_CLIENT_ID=
BITBUCKET_OAUTH_CLIENT_SECRET=
```

Restart Flask → **Data & integrations** → **Bitbucket** → **OAuth**.

## Next

**#4 Google Workspace** after Bitbucket works.
