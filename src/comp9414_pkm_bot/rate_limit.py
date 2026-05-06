from __future__ import annotations

import time
from collections import deque


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = {}

    def allow(self, chat_id: int) -> bool:
        now = time.monotonic()
        bucket = self._events.setdefault(chat_id, deque())
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_events:
            return False
        bucket.append(now)
        return True
