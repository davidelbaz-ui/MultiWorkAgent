# Agent: Anthropic Claude (production)

MultiWorkAgent can use **Claude** instead of **Gemini** for chat replies. Configuration is env-only (no code deploy beyond what is already in `agent_executor.py`).

## 1. Get an API key

1. Sign in at [console.anthropic.com](https://console.anthropic.com/).
2. **Settings** → **API keys** (or **Get API keys** from the dashboard).
3. **Create key** → copy the value (`sk-ant-…`). Store it only in Vercel / local `.env`, never in git.

Add billing/credits in the Anthropic console if the account has no balance.

## 2. Vercel (production)

Project → **Settings** → **Environment Variables** → **Production**:

| Variable | Value |
|----------|--------|
| `AGENT_PROVIDER` | `anthropic` |
| `ANTHROPIC_API_KEY` | your `sk-ant-…` key |
| `AGENT_MODEL` | optional; default in code is `claude-sonnet-4-20250514` |

If you still have `GEMINI_API_KEY` set, **`AGENT_PROVIDER=anthropic` is required** — otherwise auto-detection may prefer Gemini when only `AGENT_API_KEY` is ambiguous.

Recommended while on Claude:

- Leave `GEMINI_API_KEY` unset on Production **or** keep it for a future switch but always set `AGENT_PROVIDER`.
- Set `AGENT_MOCK=0`.

**Redeploy** after saving env vars.

## 3. Local `.env`

```env
AGENT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
AGENT_MODEL=claude-sonnet-4-20250514
AGENT_MOCK=0
```

Restart Flask (`python app.py`).

## 4. Verify

1. Open the agent, send a short message.
2. If misconfigured you’ll see: *Set ANTHROPIC_API_KEY and restart the app.*
3. Admin / run logs should show the configured model name.

## Behavior vs Gemini

| Feature | Gemini (`AGENT_PROVIDER=gemini`) | Claude (`AGENT_PROVIDER=anthropic`) |
|--------|-----------------------------------|-------------------------------------|
| Chat + product/knowledge context | Yes | Yes |
| **Live integration/database tools** (Slack, Salesforce, etc.) | Yes, when one business is selected | **No** — single Messages API call, no tool loop yet |
| Image attachments in chat | Sent to model | Text-only path today (images not attached to Claude payload) |

For full **Connect → agent operates integrations** behavior, keep **Gemini** until an Anthropic tool loop is added.

## Optional tuning

| Variable | Default | Notes |
|----------|---------|--------|
| `AGENT_RUN_INPUT_CAP` | 30000 | Metering cap |
| `AGENT_RUN_OUTPUT_CAP` | 2000 | Max output tokens |
| `AGENT_REQUEST_TIMEOUT` | 90 | Seconds |
| `AGENT_INTEGRATION_TOOLS` | 1 | Affects Gemini tool path only |
| `AGENT_DAILY_RUN_LIMIT` | 50 | Per account rolling 24h |

## Switch back to Gemini

Set `AGENT_PROVIDER=gemini`, ensure `GEMINI_API_KEY` is set, redeploy.
