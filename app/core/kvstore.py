"""Tiny key-value abstraction used for duplicate-message protection and rate limiting.

Uses Redis when REDIS_URL is configured (needed when running more than one instance),
otherwise an in-memory store with TTLs (fine for a single instance and for tests).
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol


class KVStore(Protocol):
    async def set_if_absent(self, key: str, ttl_seconds: int) -> bool: ...
    async def incr(self, key: str, ttl_seconds: int) -> int: ...
    async def close(self) -> None: ...


class MemoryKVStore:
    def __init__(self, clock=time.monotonic, max_keys: int = 100_000):
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()
        self._clock = clock
        self._max_keys = max_keys

    def _purge(self, now: float) -> None:
        if len(self._data) < self._max_keys:
            return
        for k in [k for k, (_, exp) in self._data.items() if exp <= now]:
            del self._data[k]

    async def set_if_absent(self, key: str, ttl_seconds: int) -> bool:
        async with self._lock:
            now = self._clock()
            self._purge(now)
            current = self._data.get(key)
            if current and current[1] > now:
                return False
            self._data[key] = (1, now + ttl_seconds)
            return True

    async def incr(self, key: str, ttl_seconds: int) -> int:
        async with self._lock:
            now = self._clock()
            self._purge(now)
            value, exp = self._data.get(key, (0, 0.0))
            if exp <= now:
                value, exp = 0, now + ttl_seconds
            value += 1
            self._data[key] = (value, exp)
            return value

    async def close(self) -> None:
        self._data.clear()


class RedisKVStore:
    def __init__(self, url: str):
        from redis import asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=True)

    async def set_if_absent(self, key: str, ttl_seconds: int) -> bool:
        return bool(await self._redis.set(key, "1", nx=True, ex=ttl_seconds))

    async def incr(self, key: str, ttl_seconds: int) -> int:
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds, nx=True)
        value, _ = await pipe.execute()
        return int(value)

    async def close(self) -> None:
        await self._redis.aclose()


def build_kv_store(redis_url: str | None) -> KVStore:
    return RedisKVStore(redis_url) if redis_url else MemoryKVStore()


class RateLimiter:
    """Fixed-window limiter: at most `limit` events per `window` seconds per key."""

    def __init__(self, store: KVStore, limit: int, window_seconds: int = 60, prefix: str = "rl"):
        self.store, self.limit, self.window, self.prefix = store, limit, window_seconds, prefix

    async def hit(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, count_in_window)."""
        bucket = int(time.time() // self.window)
        count = await self.store.incr(f"{self.prefix}:{key}:{bucket}", self.window + 5)
        return count <= self.limit, count


class Deduplicator:
    """Remembers WhatsApp message IDs so Meta's webhook retries are processed only once."""

    def __init__(self, store: KVStore, ttl_seconds: int = 2 * 24 * 3600):
        self.store, self.ttl = store, ttl_seconds

    async def first_time(self, message_id: str) -> bool:
        return await self.store.set_if_absent(f"wamid:{message_id}", self.ttl)
