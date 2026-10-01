"""Simple in-memory HTTP rate limits (per client IP)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque

_lock = threading.Lock()
_buckets: dict[str, Deque[float]] = defaultdict(deque)


def _client_key(prefix: str, remote_addr: str | None) -> str:
    return f"{prefix}:{remote_addr or 'unknown'}"


def _prune(bucket: Deque[float], *, window_seconds: float, now: float) -> None:
    cutoff = now - window_seconds
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()


def allow(
    prefix: str,
    remote_addr: str | None,
    *,
    max_events: int,
    window_seconds: float = 60.0,
) -> bool:
    if max_events <= 0:
        return True
    now = time.monotonic()
    key = _client_key(prefix, remote_addr)
    with _lock:
        bucket = _buckets[key]
        _prune(bucket, window_seconds=window_seconds, now=now)
        if len(bucket) >= max_events:
            return False
        bucket.append(now)
        return True


def reset_for_tests() -> None:
    with _lock:
        _buckets.clear()
