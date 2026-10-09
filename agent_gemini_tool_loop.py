"""Gemini generateContent with function calling and agent operation tools."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import agent_operation_tools
import agent_tool_trace

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_post(
    *,
    api_key: str,
    model: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _text_from_parts(parts: list[dict[str, Any]]) -> str:
    return "\n".join(str(p.get("text", "")) for p in parts if p.get("text")).strip()


def _function_calls_from_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for part in parts:
        fc = part.get("functionCall")
        if isinstance(fc, dict) and fc.get("name"):
            calls.append(fc)
    return calls


def run_gemini_with_operation_tools(
    *,
    api_key: str,
    model: str,
    system: str,
    contents: list[dict[str, Any]],
    ctx: agent_operation_tools.OperationContext,
    scope_label: str,
    business_name: str | None,
    message_count: int,
    generation_config: dict[str, Any],
    timeout: float,
    retry_status_codes: frozenset[int],
    retry_attempts: int,
    cancel_event: Any | None = None,
) -> tuple[str, int, int, str | None, list[dict[str, Any]]]:
    """
    Returns (content, input_tokens, output_tokens, finish_reason, tool_trace_rows).
    tool_trace_rows are dicts suitable to merge into build_chat_run_tool_calls via executed_tool_call.
    """
    tools_payload = {
        "functionDeclarations": agent_operation_tools.gemini_function_declarations(),
    }
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": list(contents),
        "generationConfig": generation_config,
        "tools": [tools_payload],
    }

    executed_traces: list[dict[str, Any]] = []
    input_tokens = 0
    output_tokens = 0
    finish_reason: str | None = None

    for _round in range(agent_operation_tools.max_tool_rounds()):
        if cancel_event is not None and getattr(cancel_event, "is_set", None) and cancel_event.is_set():
            raise InterruptedError("cancelled")

        data: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt in range(retry_attempts):
            try:
                data = _gemini_post(api_key=api_key, model=model, payload=payload, timeout=timeout)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in retry_status_codes and attempt + 1 < retry_attempts:
                    time.sleep(0.75 * (attempt + 1))
                    continue
                raise
            except (urllib.error.URLError, socket.timeout) as exc:
                last_exc = exc
                break
        if data is None:
            if last_exc:
                raise last_exc
            raise RuntimeError("Gemini request failed.")

        if data.get("error"):
            err = data["error"]
            message = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(message)

        usage = data.get("usageMetadata") or {}
        input_tokens = int(usage.get("promptTokenCount") or input_tokens)
        output_tokens = int(usage.get("candidatesTokenCount") or output_tokens)

        candidates = data.get("candidates") or []
        if not candidates:
            return "The agent returned no candidates.", input_tokens, output_tokens, finish_reason, executed_traces

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        parts = (candidate.get("content") or {}).get("parts") or []
        function_calls = _function_calls_from_parts(parts)

        if not function_calls:
            text = _text_from_parts(parts)
            return text or "The agent returned an empty response.", input_tokens, output_tokens, finish_reason, executed_traces

        payload["contents"].append({"role": "model", "parts": parts})

        response_parts: list[dict[str, Any]] = []
        for fc in function_calls:
            name = str(fc.get("name") or "")
            args = fc.get("args") if isinstance(fc.get("args"), dict) else {}
            try:
                result = agent_operation_tools.execute_tool(ctx, name, args)
                status = "ok" if result.get("ok") is not False and "error" not in result else "error"
            except Exception as exc:
                result = {"ok": False, "error": str(exc)}
                status = "error"
            executed_traces.append(
                agent_tool_trace.executed_tool_call(
                    name=name,
                    arguments=args,
                    result=result,
                    status=status,
                )
            )
            response_parts.append(
                {
                    "functionResponse": {
                        "name": name,
                        "response": result,
                    }
                }
            )

        payload["contents"].append({"role": "function", "parts": response_parts})

    return (
        "The agent reached the maximum number of tool steps. Summarize what was done and what is left.",
        input_tokens,
        output_tokens,
        "MAX_TOOL_ROUNDS",
        executed_traces,
    )
