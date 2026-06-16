"""Tiny in-memory fixed-window rate limiter.

Single-process uvicorn, so a process-local dict is enough — no Redis. Used to
stop brute-forcing the deploy token; legit deploys are one POST occasionally.
"""
import time
from collections import defaultdict, deque

from fastapi import Request


class FixedWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record a hit for `key`; return False if it exceeds the window limit."""
        now = time.monotonic()
        hits = self._hits[key]
        cutoff = now - self.window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


def client_ip(request: Request) -> str:
    """Real client IP behind nginx/Cloudflare (leftmost X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
