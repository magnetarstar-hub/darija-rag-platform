import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class SlidingWindowLimiter:
    """In-memory limiter (per process). For multi-replica deployments swap for a Redis-backed one."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: float = 60.0) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(429, "Too many requests", headers={"Retry-After": str(int(window_s))})
            q.append(now)
