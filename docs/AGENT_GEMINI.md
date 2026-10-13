# Agent: Google Gemini (production default)

MultiWorkAgent uses **Gemini** by default for chat, knowledge context, and **live integration/database tools** when one business is selected.

## 1. Get an API key

1. Open [Google AI Studio](https://aistudio.google.com/apikey) (or Google Cloud with Generative Language API).
2. Create an API key.
3. Store it only in Vercel / local `.env`, never in git.

## 2. Vercel (production)

Project → **Settings** → **Environment Variables** → **Production**:

| Variable | Value |
|----------|--------|
| `AGENT_PROVIDER` | `gemini` |
| `GEMINI_API_KEY` | your key |
| `AGENT_MODEL` | optional; default `gemini-3.8-flash` |
| `AGENT_MODEL_FALLBACK` | optional; default `gemini-2.5-flash` |
| `AGENT_MOCK` | `0` |

If you also set `ANTHROPIC_API_KEY`, keep **`AGENT_PROVIDER=gemini`** so the app does not auto-select Claude.

**Redeploy** after saving env vars.

## 3. Local `.env`

```env
AGENT_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
AGENT_MODEL=gemini-3.8-flash
AGENT_MODEL_FALLBACK=gemini-2.5-flash
AGENT_MOCK=0
```

Restart Flask (`python app.py`).

## 4. Verify

1. Open **Agent**, select a business if testing integrations, send a short message.
2. Misconfigured: *Set GEMINI_API_KEY or AGENT_API_KEY and restart the app.*
3. `/health` → `deployment.agent.provider: "gemini"`, `ready: true`.

## Optional tuning

| Variable | Default | Notes |
|----------|---------|--------|
| `AGENT_INTEGRATION_TOOLS` | `1` | Tool loop for connected integrations |
| `AGENT_RUN_INPUT_CAP` | 30000 | Metering cap |
| `AGENT_RUN_OUTPUT_CAP` | 2000 | Max output tokens |
| `AGENT_REQUEST_TIMEOUT` | 90 | Seconds |

## Claude instead

See [AGENT_CLAUDE.md](AGENT_CLAUDE.md). Claude is chat-only today (no integration tool loop).
