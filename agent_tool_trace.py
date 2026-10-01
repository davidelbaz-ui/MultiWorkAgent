"""Build per-run tool call traces for logging and the run inspector."""

from __future__ import annotations

import json
from typing import Any


def _json_safe(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def scope_context_call(*, scope_label: str, business_name: str | None, message_count: int) -> dict[str, Any]:
    return {
        "tool_name": "context.scope",
        "input": {
            "scope_label": scope_label,
            "business_name": business_name,
        },
        "output": {
            "message_count": message_count,
        },
        "status": "ok",
    }


def llm_messages_call(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    text_chars: int,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "tool_name": "llm.messages",
        "input": {"model": model},
        "output": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "text_chars": text_chars,
            "stop_reason": stop_reason,
        },
        "status": "ok",
    }


def model_tool_use_call(*, tool_id: str, name: str, tool_input: Any) -> dict[str, Any]:
    return {
        "tool_name": name,
        "input": {"tool_use_id": tool_id, "arguments": tool_input},
        "output": None,
        "status": "requested",
    }


def build_chat_run_tool_calls(
    *,
    scope_label: str,
    business_name: str | None,
    message_count: int,
    model: str,
    input_tokens: int,
    output_tokens: int,
    text_chars: int,
    stop_reason: str | None,
    model_tool_uses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = [
        scope_context_call(
            scope_label=scope_label,
            business_name=business_name,
            message_count=message_count,
        ),
    ]
    for tool_use in model_tool_uses:
        calls.append(
            model_tool_use_call(
                tool_id=str(tool_use.get("id") or ""),
                name=str(tool_use.get("name") or "unknown"),
                tool_input=tool_use.get("input"),
            )
        )
    calls.append(
        llm_messages_call(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            text_chars=text_chars,
            stop_reason=stop_reason,
        )
    )
    return calls


def tool_call_display_label(row: dict[str, Any]) -> str:
    name = row.get("tool_name") or row.get("name") or "tool"
    status = row.get("status") or "unknown"
    return f"{name} · {status}"
