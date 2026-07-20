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
