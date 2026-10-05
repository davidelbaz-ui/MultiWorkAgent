"""In-memory log ring for the local admin console (per process)."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any

_BUFFER: deque[dict[str, Any]] = deque(maxlen=800)
_LOCK = threading.Lock()
_INSTALLED = False


class AdminLogBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload: dict[str, Any] = {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            extra = getattr(record, "structured", None)
            if isinstance(extra, dict):
                payload["fields"] = extra
            if record.exc_info:
                payload["exc_info"] = logging.Formatter().formatException(record.exc_info)
            with _LOCK:
                _BUFFER.appendleft(payload)
        except Exception:
            self.handleError(record)


def install_log_buffer(root: logging.Logger | None = None) -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    target = root or logging.getLogger()
    handler = AdminLogBufferHandler()
    handler.setLevel(logging.INFO)
    target.addHandler(handler)
    _INSTALLED = True


def recent_logs(*, limit: int = 200, level: str | None = None) -> list[dict[str, Any]]:
    cap = max(1, min(limit, 500))
    level_upper = (level or "").strip().upper()
    with _LOCK:
        rows = list(_BUFFER)
    if level_upper:
        rows = [row for row in rows if row.get("level") == level_upper]
    return rows[:cap]
