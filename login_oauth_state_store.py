"""One-time OAuth state tokens for login (Google / Microsoft)."""

from __future__ import annotations

import signed_oauth_state

STATE_TTL_SECONDS = signed_oauth_state.DEFAULT_MAX_AGE_SECONDS
_LOGIN_STATE_SALT = "multiworkagent-login-oauth-state"


def bootstrap() -> None:
    """No-op (state is signed; no database required)."""


def create_state(*, provider: str, next_url: str = "") -> str:
    return signed_oauth_state.issue_signed_state(
        salt=_LOGIN_STATE_SALT,
        payload={
            "provider": provider,
            "next_url": next_url or "",
        },
        max_age_seconds=STATE_TTL_SECONDS,
    )


def pop_state(state_token: str) -> dict[str, str] | None:
    data = signed_oauth_state.loads_signed_state(
        salt=_LOGIN_STATE_SALT,
        token=state_token,
        max_age_seconds=STATE_TTL_SECONDS,
    )
    if not data:
        return None
    provider = str(data.get("provider") or "")
    if not provider:
        return None
    return {
        "state_token": state_token,
        "provider": provider,
        "next_url": str(data.get("next_url") or ""),
        "created_at": "",
    }
