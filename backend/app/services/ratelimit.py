"""A tiny in-process rate limiter for login attempts (CLAUDE.md A04).

This is a single-node, in-memory fixed-window limiter — adequate for the MVP.
For multi-node production, back it with Redis. Keyed by (identifier), where the
caller chooses the identifier (email+IP) to blunt both credential stuffing and
account-targeted brute force.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Window:
    count: int = 0
    reset_at: float = 0.0
    locked_until: float = 0.0
    strikes: int = 0


@dataclass
class RateLimiter:
    max_attempts: int
    window_seconds: int
    _buckets: dict[str, _Window] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Call before verifying creds."""
        now = time.monotonic() if now is None else now
        with self._lock:
            w = self._buckets.get(key)
            if w is None:
                return True, 0
            if w.locked_until and now < w.locked_until:
                return False, int(w.locked_until - now) + 1
            if w.reset_at and now >= w.reset_at:
                # window expired -> clear counting but keep strike history briefly
                w.count = 0
                w.reset_at = 0.0
            if w.count >= self.max_attempts:
                # exponential backoff lockout on repeated exhaustion
                w.strikes += 1
                w.locked_until = now + min(self.window_seconds * (2 ** (w.strikes - 1)), 3600)
                return False, int(w.locked_until - now) + 1
            return True, 0

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            w = self._buckets.setdefault(key, _Window())
            if not w.reset_at or now >= w.reset_at:
                w.count = 0
                w.reset_at = now + self.window_seconds
            w.count += 1

    def reset(self, key: str) -> None:
        """Clear on successful auth."""
        with self._lock:
            self._buckets.pop(key, None)


class RedisRateLimiter:
    """Shared fixed-window limiter backed by Redis, so limits hold across app
    instances (horizontal scaling, CLAUDE.md A04). Same interface as
    RateLimiter. Fails OPEN on a Redis outage — availability over a hard cap —
    which is the right tradeoff for a login limiter (the in-memory node-local
    limiter still applies if you keep one, and a full outage is rare)."""

    def __init__(self, client, max_attempts: int, window_seconds: int) -> None:  # noqa: ANN001
        self._r = client
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def _k(self, key: str) -> str:
        return f"rl:{key}"

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        try:
            count = self._r.get(self._k(key))
            if count is None:
                return True, 0
            if int(count) >= self.max_attempts:
                ttl = self._r.ttl(self._k(key))
                return False, (int(ttl) + 1 if ttl and ttl > 0 else self.window_seconds)
            return True, 0
        except Exception:  # noqa: BLE001 — fail open on Redis trouble
            return True, 0

    def record_failure(self, key: str, now: float | None = None) -> None:
        try:
            pipe = self._r.pipeline()
            pipe.incr(self._k(key))
            pipe.expire(self._k(key), self.window_seconds, nx=True)
            pipe.execute()
        except Exception:  # noqa: BLE001
            pass

    def reset(self, key: str) -> None:
        try:
            self._r.delete(self._k(key))
        except Exception:  # noqa: BLE001
            pass


_redis_client = None


def make_rate_limiter(max_attempts: int, window_seconds: int):
    """Return a Redis-backed limiter if VOLTPHISH_REDIS_URL is set, else the
    in-memory one. Lazily builds a single shared Redis client."""
    global _redis_client
    from ..config import get_settings

    url = get_settings().redis_url
    if not url:
        return RateLimiter(max_attempts=max_attempts, window_seconds=window_seconds)
    if _redis_client is None:
        import redis  # lazy — only needed when configured

        _redis_client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
    return RedisRateLimiter(_redis_client, max_attempts, window_seconds)
