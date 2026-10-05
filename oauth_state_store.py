"""One-time OAuth state tokens (CSRF protection for provider redirects)."""

from __future__ import annotations

from typing import Any

import signed_oauth_state

STATE_TTL_SECONDS = signed_oauth_state.DEFAULT_MAX_AGE_SECONDS
_INTEGRATION_STATE_SALT = "multiworkagent-integration-oauth-state"


def bootstrap() -> None:
    """No-op (state is signed; no database required)."""


def create_state(
    *,
    account_id: str,
    business_id: str,
    provider_slug: str,
) -> str:
    return signed_oauth_state.issue_signed_state(
        salt=_INTEGRATION_STATE_SALT,
        payload={
            "account_id": account_id,
            "business_id": business_id,
            "provider_slug": provider_slug,
        },
        max_age_seconds=STATE_TTL_SECONDS,
    )


def pop_state(state_token: str) -> dict[str, Any] | None:
    data = signed_oauth_state.loads_signed_state(
        salt=_INTEGRATION_STATE_SALT,
        token=state_token,
        max_age_seconds=STATE_TTL_SECONDS,
    )
    if not data:
        return None
    account_id = str(data.get("account_id") or "")
    business_id = str(data.get("business_id") or "")
    provider_slug = str(data.get("provider_slug") or "")
    if not account_id or not business_id or not provider_slug:
        return None
    return {
        "state_token": state_token,
        "account_id": account_id,
        "business_id": business_id,
        "provider_slug": provider_slug,
        "created_at": "",
    }
