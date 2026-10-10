"""Format stored UTC timestamps for the operator admin UI (US Eastern)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_EASTERN = ZoneInfo("America/New_York")


def format_eastern(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_EASTERN)
    abbr = "EDT" if local.dst() else "EST"
    return local.strftime(f"%b %d, %Y %I:%M %p {abbr}")
