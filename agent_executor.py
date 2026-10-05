"""Invoke the platform agent after a user message (Gemini or Anthropic)."""

from __future__ import annotations

import base64
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_stream_cancel_events: dict[str, threading.Event] = {}

import agent_tool_trace
import chat_store
import knowledge_store

APP_DIR = Path(__file__).resolve().parent
_AGENT_PRODUCT_KNOWLEDGE_PATH = APP_DIR / "docs" / "AGENT_PRODUCT_KNOWLEDGE.md"
_MAX_PRODUCT_KNOWLEDGE_CHARS = 100_000
_product_knowledge_cache: tuple[int, str] | None = None

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_GEMINI_FALLBACK_MODEL = "gemini-2.5-flash"
GEMINI_RETRY_STATUS_CODES = frozenset({429, 503})
GEMINI_RETRY_ATTEMPTS = 3
DEFAULT_MAX_OUTPUT_TOKENS = 2_000
DEFAULT_TIMEOUT_SECONDS = 90.0
MAX_HISTORY_MESSAGES = 40
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class AgentRunResult:
    status: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    error_code: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "error_code": self.error_code,
            "tool_calls": self.tool_calls,
        }


def run_input_cap() -> int:
    return int(os.environ.get("AGENT_RUN_INPUT_CAP", "30000"))


def run_output_cap() -> int:
    return int(os.environ.get("AGENT_RUN_OUTPUT_CAP", "2000"))


def _agent_provider() -> str:
    explicit = (os.environ.get("AGENT_PROVIDER") or "").strip().lower()
    if explicit in ("gemini", "google"):
        return "gemini"
    if explicit in ("anthropic", "claude"):
        return "anthropic"
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if anthropic_key.startswith("sk-ant-"):
        return "anthropic"
    return "gemini"


def _gemini_api_key() -> str:
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("AGENT_API_KEY")
        or ""
    ).strip()


def _anthropic_api_key() -> str:
    return (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("AGENT_API_KEY") or "").strip()


def _model() -> str:
    raw = (os.environ.get("AGENT_MODEL") or "").strip()
    if raw:
        return raw
    if _agent_provider() == "gemini":
        return DEFAULT_GEMINI_MODEL
    return DEFAULT_ANTHROPIC_MODEL


def _gemini_fallback_model() -> str:
    raw = (os.environ.get("AGENT_MODEL_FALLBACK") or "").strip()
    return raw or DEFAULT_GEMINI_FALLBACK_MODEL


def _gemini_error_message(http_code: int, body: str) -> str:
    try:
        parsed = json.loads(body)
        err = parsed.get("error") if isinstance(parsed, dict) else None
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    except json.JSONDecodeError:
        pass
    if http_code in (429, 503):
        return (
            "The model is temporarily overloaded. Please wait a moment and try again."
        )
    return body[:400] if body else f"HTTP {http_code}"


def _gemini_generate_once(
    *,
    api_key: str,
    model: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, urllib.error.HTTPError | None, str | None]:
    body = json.dumps(payload).encode("utf-8")
    url = (
        f"{GEMINI_API_BASE}/models/{urllib.parse.quote(model, safe='')}:generateContent"
        f"?key={urllib.parse.quote(api_key, safe='')}"
    )
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_timeout_seconds()) as resp:
            return json.loads(resp.read().decode("utf-8")), None, None
    except socket.timeout:
        raise
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, exc, detail
    except urllib.error.URLError:
        raise


def _gemini_generate_with_retries(
    *,
    api_key: str,
    model: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, AgentRunResult | None]:
    last_code = 0
    last_detail = ""
    for attempt in range(GEMINI_RETRY_ATTEMPTS):
        try:
            data, http_err, detail = _gemini_generate_once(
                api_key=api_key, model=model, payload=payload
            )
        except socket.timeout:
            return None, AgentRunResult(
                status="error",
                content="The agent timed out. Try a shorter message or try again in a moment.",
                error_code="timeout",
            )
        except urllib.error.URLError as exc:
            return None, AgentRunResult(
                status="error",
                content=f"Could not reach the agent service: {exc.reason}",
                error_code="network_error",
            )
        if data is not None:
            return data, None
        assert http_err is not None
        last_code = http_err.code
        last_detail = detail or ""
        if http_err.code not in GEMINI_RETRY_STATUS_CODES:
            break
        if attempt + 1 < GEMINI_RETRY_ATTEMPTS:
            time.sleep(0.75 * (attempt + 1))
    message = _gemini_error_message(last_code, last_detail)
    code = "rate_limited" if last_code == 429 else "http_error"
    if last_code in (429, 503):
        code = "model_unavailable"
    return None, AgentRunResult(
        status="error",
        content=f"The agent request failed ({last_code}). {message}".strip(),
        error_code=code,
    )


def _timeout_seconds() -> float:
    raw = os.environ.get("AGENT_REQUEST_TIMEOUT", "")
    if raw:
        try:
            return max(5.0, float(raw))
        except ValueError:
            pass
    return DEFAULT_TIMEOUT_SECONDS


def _mock_enabled() -> bool:
    return os.environ.get("AGENT_MOCK", "").strip().lower() in ("1", "true", "yes")


def _load_product_knowledge() -> str:
    global _product_knowledge_cache
    path = _AGENT_PRODUCT_KNOWLEDGE_PATH
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        return ""
    if _product_knowledge_cache and _product_knowledge_cache[0] == mtime_ns:
        return _product_knowledge_cache[1]
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if len(text) > _MAX_PRODUCT_KNOWLEDGE_CHARS:
        text = text[:_MAX_PRODUCT_KNOWLEDGE_CHARS] + "\n\n[… product reference truncated …]"
    _product_knowledge_cache = (mtime_ns, text)
    return text


def _system_prompt(
    *,
    scope_label: str,
    business_name: str | None,
    knowledge_block: str | None = None,
) -> str:
    scope = business_name or scope_label
    prompt = (
        "You are MultiWorkAgent, an operations assistant for accounts "
        "that manage one or more businesses.\n\n"
        f"Active workspace scope: {scope}.\n"
        "Answer questions about the MultiWorkAgent product using the product reference below. "
        "Do not invent integrations or capabilities the reference does not describe. "
        "MultiWorkAgent is built for the agent to perform operational work through connected "
        "integrations and databases per business; when the user asks to change an external system, "
        "help them connect it on Data & integrations if needed and carry out the task when connections exist. "
        "Remind users to review outcomes because actions in connected systems can be wrong.\n"
        "When the user attaches images, describe and use what you see in them.\n"
        "When the user attaches text files (or business knowledge files below), use their contents.\n"
        "Be concise, practical, and use plain language."
    )
    product = _load_product_knowledge()
    if product:
        prompt += (
            "\n\n--- MultiWorkAgent product reference (authoritative for how the app works) ---\n\n"
            f"{product}"
        )
    if knowledge_block:
        prompt += (
            "\n\nBusiness knowledge files for this workspace:\n"
            f"{knowledge_block}"
        )
    return prompt


def _decode_attachment_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def _text_attachment_part(
    thread_id: str,
    message_id: int,
    att: dict[str, Any],
    *,
    max_chars: int = 100_000,
) -> dict[str, str]:
    name = att.get("original_name") or "file"
    loaded = chat_store.read_message_attachment_bytes(
        thread_id=thread_id,
        message_id=message_id,
        file_id=int(att["id"]),
        max_bytes=chat_store.MAX_INLINE_TEXT_BYTES,
    )
    if not loaded:
        return {"text": f"[Attached file could not be loaded: {name}]"}
    text = _decode_attachment_text(loaded[0])
    if len(text) > max_chars:
        text = text[:max_chars] + "\n… [truncated]"
    return {"text": f"[Attached file: {name}]\n{text}"}


def _format_user_content(thread_id: str, msg: dict[str, Any]) -> str:
    parts: list[str] = []
    if msg.get("content"):
        parts.append(str(msg["content"]))
    message_id = int(msg["id"])
    not_opened: list[str] = []
    for att in msg.get("attachments") or []:
        mime = str(att.get("mime_type") or "").lower()
        name = att.get("original_name") or "file"
        if mime.startswith("image/"):
            continue
        if chat_store.is_text_like_attachment(att.get("mime_type"), name):
            snippet = _text_attachment_part(thread_id, message_id, att)["text"]
            parts.append(snippet)
        else:
            not_opened.append(name)
    if not_opened:
        parts.append(f"[Attached files (not opened): {', '.join(not_opened)}]")
    return "\n\n".join(parts) if parts else "(empty message)"


def _gemini_user_parts(thread_id: str, msg: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if msg.get("content"):
        parts.append({"text": str(msg["content"])})
    message_id = int(msg["id"])
    for att in msg.get("attachments") or []:
        mime = str(att.get("mime_type") or "").lower()
        name = att.get("original_name") or "file"
        is_svg = mime in ("image/svg+xml", "application/svg+xml") or name.lower().endswith(
            ".svg"
        )
        if is_svg or mime.startswith("image/"):
            loaded = chat_store.read_message_attachment_bytes(
                thread_id=thread_id,
                message_id=message_id,
                file_id=int(att["id"]),
            )
            if not loaded:
                parts.append({"text": f"[Attachment could not be loaded: {name}]"})
            elif is_svg:
                try:
                    svg_text = loaded[0].decode("utf-8")
                except UnicodeDecodeError:
                    svg_text = loaded[0].decode("utf-8", errors="replace")
                parts.append(
                    {
                        "text": f"[SVG attachment: {name}]\n{svg_text[:80_000]}",
                    }
                )
            else:
                data, mime_type = loaded
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(data).decode("ascii"),
                        }
                    }
                )
        else:
            if chat_store.is_text_like_attachment(att.get("mime_type"), name):
                parts.append(_text_attachment_part(thread_id, message_id, att))
            else:
                parts.append({"text": f"[Attached file (not opened): {name}]"})
    if not parts:
        parts.append({"text": "(empty message)"})
    return parts


def _history_for_api(thread_id: str) -> list[dict[str, Any]]:
    messages = chat_store.get_thread_state(thread_id)["messages"]
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]

    api_messages: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            api_messages.append(
                {
                    "role": "user",
                    "content": _format_user_content(thread_id, msg),
                    "parts": _gemini_user_parts(thread_id, msg),
                }
            )
        elif role == "agent":
            api_messages.append({"role": "assistant", "content": msg.get("content") or ""})
        elif role == "system":
            api_messages.append(
                {
                    "role": "user",
                    "content": f"[System notice: {msg.get('content') or ''}]",
                }
            )
    return api_messages


def _mock_reply(
    thread_id: str,
    *,
    scope_label: str,
    business_name: str | None,
) -> AgentRunResult:
    state = chat_store.get_thread_state(thread_id)
    message_count = len(state["messages"])
    last_user = next((m for m in reversed(state["messages"]) if m["role"] == "user"), None)
    snippet = ""
    if last_user:
        snippet = (_format_user_content(thread_id, last_user) or "")[:500]
    content = (
        "Mock agent reply (AGENT_MOCK is enabled).\n\n"
        f"I received:\n{snippet or '(no text)'}"
    )
    input_tokens = min(len(snippet) * 2, 1200)
    output_tokens = min(len(content), 400)
    tool_calls = agent_tool_trace.build_chat_run_tool_calls(
        scope_label=scope_label,
        business_name=business_name,
        message_count=message_count,
        model="mock",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_chars=len(content),
        stop_reason="end_turn",
        model_tool_uses=[],
    )
    return AgentRunResult(
        status="completed",
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
    )


def _extract_tool_uses(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tool_uses: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("type") == "tool_use":
            tool_uses.append(
                {
                    "id": block.get("id"),
                    "name": block.get("name"),
                    "input": block.get("input"),
                }
            )
    return tool_uses


def _gemini_contents(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        if role == "user" and msg.get("parts"):
            parts = list(msg["parts"])
        else:
            text = str(msg.get("content") or "")
            parts = [{"text": text}] if text else [{"text": ""}]
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": parts})
    if contents and contents[0]["role"] != "user":
        contents.insert(0, {"role": "user", "parts": [{"text": "Hello."}]})
    return contents


def _call_gemini(
    *,
    system: str,
    messages: list[dict[str, str]],
    scope_label: str,
    business_name: str | None,
    message_count: int,
) -> AgentRunResult:
    api_key = _gemini_api_key()
    if not api_key:
        return AgentRunResult(
            status="unconfigured",
            content=(
                "Agent execution is not configured on the server. "
                "Set GEMINI_API_KEY or AGENT_API_KEY and restart the app."
            ),
            error_code="missing_api_key",
        )

    primary_model = _model()
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_contents(messages),
        "generationConfig": {
            "maxOutputTokens": min(DEFAULT_MAX_OUTPUT_TOKENS, run_output_cap()),
        },
    }

    data, err_result = _gemini_generate_with_retries(
        api_key=api_key, model=primary_model, payload=payload
    )

    model = primary_model
    if data is None:
        fallback = _gemini_fallback_model()
        if fallback and fallback != primary_model and err_result:
            data, fallback_err = _gemini_generate_with_retries(
                api_key=api_key, model=fallback, payload=payload
            )
            if data is not None:
                model = fallback
            elif fallback_err:
                err_result = fallback_err
        if data is None:
            return err_result or AgentRunResult(
                status="error",
                content="The agent request failed.",
                error_code="http_error",
            )

    if data.get("error"):
        err = data["error"]
        message = err.get("message") if isinstance(err, dict) else str(err)
        return AgentRunResult(
            status="error",
            content=f"The agent request failed. {message}",
            error_code="api_error",
        )

    candidates = data.get("candidates") or []
    content = ""
    finish_reason = None
    if candidates:
        finish_reason = candidates[0].get("finishReason")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        content = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
    if not content:
        block = (candidates[0].get("finishReason") if candidates else None) or "unknown"
        content = f"The agent returned an empty response ({block})."

    usage = data.get("usageMetadata") or {}
    input_tokens = int(usage.get("promptTokenCount") or 0)
    output_tokens = int(usage.get("candidatesTokenCount") or 0)
    tool_calls = agent_tool_trace.build_chat_run_tool_calls(
        scope_label=scope_label,
        business_name=business_name,
        message_count=message_count,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_chars=len(content),
        stop_reason=finish_reason,
        model_tool_uses=[],
    )
    return AgentRunResult(
        status="completed",
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
    )


def _call_anthropic(
    *,
    system: str,
    messages: list[dict[str, str]],
    scope_label: str,
    business_name: str | None,
    message_count: int,
) -> AgentRunResult:
    api_key = _anthropic_api_key()
    if not api_key:
        return AgentRunResult(
            status="unconfigured",
            content=(
                "Agent execution is not configured on the server. "
                "Set ANTHROPIC_API_KEY and restart the app."
            ),
            error_code="missing_api_key",
        )

    payload = {
        "model": _model(),
        "max_tokens": min(DEFAULT_MAX_OUTPUT_TOKENS, run_output_cap()),
        "system": system,
        "messages": messages,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=_timeout_seconds()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except socket.timeout:
        return AgentRunResult(
            status="error",
            content="The agent timed out. Try a shorter message or try again in a moment.",
            error_code="timeout",
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        return AgentRunResult(
            status="error",
            content=f"The agent request failed ({exc.code}). {detail}".strip(),
            error_code="http_error",
        )
    except urllib.error.URLError as exc:
        return AgentRunResult(
            status="error",
            content=f"Could not reach the agent service: {exc.reason}",
            error_code="network_error",
        )

    blocks = data.get("content") or []
    text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    content = "\n".join(part for part in text_parts if part).strip()
    if not content and not _extract_tool_uses(blocks):
        content = "The agent returned an empty response."

    usage = data.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    tool_calls = agent_tool_trace.build_chat_run_tool_calls(
        scope_label=scope_label,
        business_name=business_name,
        message_count=message_count,
        model=_model(),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        text_chars=len(content),
        stop_reason=data.get("stop_reason"),
        model_tool_uses=_extract_tool_uses(blocks),
    )
    return AgentRunResult(
        status="completed",
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
    )


def attach_stream_cancel(run_id: str) -> threading.Event:
    event = threading.Event()
    _stream_cancel_events[run_id] = event
    return event


def request_stream_cancel(run_id: str) -> None:
    event = _stream_cancel_events.get(run_id)
    if event:
        event.set()


def detach_stream_cancel(run_id: str) -> None:
    _stream_cancel_events.pop(run_id, None)


def _gemini_chunk_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for cand in data.get("candidates") or []:
        content = cand.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                parts.append(str(text))
    return "".join(parts)


def _iter_gemini_stream_chunks(
    *,
    api_key: str,
    model: str,
    payload: dict[str, Any],
    cancel_event: threading.Event | None,
) -> Iterator[tuple[str, dict[str, Any] | None]]:
    body = json.dumps(payload).encode("utf-8")
    url = (
        f"{GEMINI_API_BASE}/models/{urllib.parse.quote(model, safe='')}:streamGenerateContent"
        f"?alt=sse&key={urllib.parse.quote(api_key, safe='')}"
    )
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=_timeout_seconds()) as resp:
        while True:
            if cancel_event and cancel_event.is_set():
                return
            line = resp.readline()
            if not line:
                break
            decoded = line.decode("utf-8", errors="replace").strip()
            if not decoded or decoded.startswith(":"):
                continue
            if decoded.startswith("data:"):
                decoded = decoded[5:].strip()
            if not decoded or decoded == "[DONE]":
                continue
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                continue
            text = _gemini_chunk_text(data)
            usage = data.get("usageMetadata")
            if text:
                yield text, usage
            elif usage:
                yield "", usage


def _agent_system_prompt(
    *,
    scope_label: str,
    business_name: str | None,
    account_id: str | None,
    business_id: str | None,
) -> str:
    knowledge = ""
    if account_id and business_id:
        knowledge = knowledge_store.build_agent_knowledge_block(
            account_id,
            business_id=business_id,
        )
    return _system_prompt(
        scope_label=scope_label,
        business_name=business_name,
        knowledge_block=knowledge or None,
    )


def stream_generate_reply(
    thread_id: str,
    *,
    scope_label: str,
    business_name: str | None = None,
    account_id: str | None = None,
    business_id: str | None = None,
    cancel_event: threading.Event | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield stream events: delta, done (with AgentRunResult fields), or error."""
    if _mock_enabled():
        result = _mock_reply(
            thread_id,
            scope_label=scope_label,
            business_name=business_name,
        )
        if result.content:
            yield {"event": "delta", "text": result.content}
        yield {"event": "done", "result": result}
        return

    api_messages = _history_for_api(thread_id)
    if not api_messages:
        yield {
            "event": "done",
            "result": AgentRunResult(
                status="error",
                content="No messages to respond to.",
                error_code="empty_thread",
            ),
        }
        return

    message_count = len(api_messages)
    system = _agent_system_prompt(
        scope_label=scope_label,
        business_name=business_name,
        account_id=account_id,
        business_id=business_id,
    )

    if _agent_provider() != "gemini":
        result = _call_anthropic(
            system=system,
            messages=api_messages,
            scope_label=scope_label,
            business_name=business_name,
            message_count=message_count,
        )
        if result.status == "completed" and result.content:
            yield {"event": "delta", "text": result.content}
        yield {"event": "done", "result": result}
        return

    api_key = _gemini_api_key()
    if not api_key:
        yield {
            "event": "done",
            "result": AgentRunResult(
                status="unconfigured",
                content=(
                    "Agent execution is not configured on the server. "
                    "Set GEMINI_API_KEY or AGENT_API_KEY and restart the app."
                ),
                error_code="missing_api_key",
            ),
        }
        return

    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _gemini_contents(api_messages),
        "generationConfig": {
            "maxOutputTokens": min(DEFAULT_MAX_OUTPUT_TOKENS, run_output_cap()),
        },
    }

    primary_model = _model()
    models_to_try = [primary_model]
    fallback = _gemini_fallback_model()
    if fallback and fallback != primary_model:
        models_to_try.append(fallback)

    last_error: AgentRunResult | None = None
    for model in models_to_try:
        if cancel_event and cancel_event.is_set():
            yield {
                "event": "done",
                "result": AgentRunResult(
                    status="error",
                    content="",
                    error_code="cancelled",
                ),
            }
            return
        accumulated: list[str] = []
        input_tokens = 0
        output_tokens = 0
        finish_reason = None
        try:
            for attempt in range(GEMINI_RETRY_ATTEMPTS):
                if cancel_event and cancel_event.is_set():
                    break
                try:
                    stream = _iter_gemini_stream_chunks(
                        api_key=api_key,
                        model=model,
                        payload=payload,
                        cancel_event=cancel_event,
                    )
                    stream_so_far = ""
                    for text, usage in stream:
                        if cancel_event and cancel_event.is_set():
                            break
                        if text:
                            piece = text
                            if stream_so_far and text.startswith(stream_so_far):
                                piece = text[len(stream_so_far) :]
                                stream_so_far = text
                            else:
                                stream_so_far += piece
                            if piece:
                                accumulated.append(piece)
                                yield {"event": "delta", "text": piece}
                        if usage:
                            input_tokens = int(usage.get("promptTokenCount") or input_tokens)
                            output_tokens = int(
                                usage.get("candidatesTokenCount") or output_tokens
                            )
                    break
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", errors="replace")
                    if exc.code in GEMINI_RETRY_STATUS_CODES and attempt + 1 < GEMINI_RETRY_ATTEMPTS:
                        time.sleep(0.75 * (attempt + 1))
                        continue
                    last_error = AgentRunResult(
                        status="error",
                        content=f"The agent request failed ({exc.code}). {_gemini_error_message(exc.code, detail)}",
                        error_code="model_unavailable" if exc.code in (429, 503) else "http_error",
                    )
                    accumulated = []
                    break
                except (urllib.error.URLError, socket.timeout) as exc:
                    reason = getattr(exc, "reason", None) or str(exc)
                    last_error = AgentRunResult(
                        status="error",
                        content=f"Could not reach the agent service: {reason}",
                        error_code="network_error",
                    )
                    accumulated = []
                    break
            if last_error and not accumulated:
                continue
            if cancel_event and cancel_event.is_set():
                content = "".join(accumulated)
                yield {
                    "event": "done",
                    "result": AgentRunResult(
                        status="error",
                        content=content,
                        error_code="cancelled",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    ),
                }
                return
            if accumulated or not last_error:
                content = "".join(accumulated).strip()
                if not content:
                    content = "The agent returned an empty response."
                tool_calls = agent_tool_trace.build_chat_run_tool_calls(
                    scope_label=scope_label,
                    business_name=business_name,
                    message_count=message_count,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    text_chars=len(content),
                    stop_reason=finish_reason,
                    model_tool_uses=[],
                )
                yield {
                    "event": "done",
                    "result": AgentRunResult(
                        status="completed",
                        content=content,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        tool_calls=tool_calls,
                    ),
                }
                return
        except Exception:
            last_error = AgentRunResult(
                status="error",
                content="The agent request failed unexpectedly.",
                error_code="http_error",
            )

    yield {
        "event": "done",
        "result": last_error
        or AgentRunResult(
            status="error",
            content="The agent request failed.",
            error_code="http_error",
        ),
    }


def generate_reply(
    thread_id: str,
    *,
    scope_label: str,
    business_name: str | None = None,
    account_id: str | None = None,
    business_id: str | None = None,
) -> AgentRunResult:
    if _mock_enabled():
        return _mock_reply(
            thread_id,
            scope_label=scope_label,
            business_name=business_name,
        )

    api_messages = _history_for_api(thread_id)
    if not api_messages:
        return AgentRunResult(
            status="error",
            content="No messages to respond to.",
            error_code="empty_thread",
        )

    message_count = len(api_messages)
    system = _agent_system_prompt(
        scope_label=scope_label,
        business_name=business_name,
        account_id=account_id,
        business_id=business_id,
    )
    if _agent_provider() == "gemini":
        return _call_gemini(
            system=system,
            messages=api_messages,
            scope_label=scope_label,
            business_name=business_name,
            message_count=message_count,
        )
    return _call_anthropic(
        system=system,
        messages=api_messages,
        scope_label=scope_label,
        business_name=business_name,
        message_count=message_count,
    )
