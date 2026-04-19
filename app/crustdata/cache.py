from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from redis import Redis

from app.core.redis_client import get_redis_client


@dataclass
class CacheEntry:
    value: dict[str, Any]
    expires_at: float


class InMemoryCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.time():
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        with self._lock:
            self._entries[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl_seconds,
            )


class CacheBackend:
    def __init__(
        self,
        *,
        redis_client: Redis | None = None,
        fallback: InMemoryCache | None = None,
    ) -> None:
        self.redis_client = redis_client
        self.fallback = fallback or InMemoryCache()

    def get(self, key: str) -> dict[str, Any] | None:
        if self.redis_client is not None:
            try:
                value = self.redis_client.get(key)
            except Exception:
                value = None
            else:
                if value is not None:
                    return json.loads(value)

        return self.fallback.get(key)

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if self.redis_client is not None:
            try:
                self.redis_client.setex(key, ttl_seconds, json.dumps(value))
                return
            except Exception:
                pass

        self.fallback.set(key, value, ttl_seconds)


def build_cache_backend() -> CacheBackend:
    try:
        redis_client = get_redis_client()
        redis_client.ping()
    except Exception:
        redis_client = None
    return CacheBackend(redis_client=redis_client)
