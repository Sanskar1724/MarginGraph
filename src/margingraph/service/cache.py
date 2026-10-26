"""Key-value cache: Redis when REDIS_URL is set, otherwise in-process memory.

Values are JSON. The in-memory cache is per process, which is fine for one
instance; run several instances behind a load balancer with Redis so they share
response caches and rate-limit counters.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any

log = logging.getLogger("margingraph.cache")


class MemoryCache:
    backend = "memory"

    def __init__(self, max_items: int = 50_000):
        self._d: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.max_items = max_items

    def get(self, key: str) -> Any | None:
        with self._lock:
            hit = self._d.get(key)
            if hit is None:
                return None
            exp, val = hit
            if exp and exp < time.monotonic():
                del self._d[key]
                return None
            self._d.move_to_end(key)
            return val

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._d[key] = (time.monotonic() + ttl if ttl else 0.0, value)
            self._d.move_to_end(key)
            while len(self._d) > self.max_items:
                self._d.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._d.pop(key, None)

    def incr(self, key: str, ttl: float) -> int:
        """Increment a counter; the TTL starts when the key is created."""
        with self._lock:
            hit = self._d.get(key)
            now = time.monotonic()
            if hit is None or (hit[0] and hit[0] < now):
                self._d[key] = (now + ttl, 1)
                return 1
            self._d[key] = (hit[0], hit[1] + 1)
            return hit[1] + 1

    def ping(self) -> bool:
        return True


class RedisCache:
    backend = "redis"

    def __init__(self, url: str, prefix: str = "mg:"):
        import redis

        self.r = redis.Redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=1.0, decode_responses=True)
        self.prefix = prefix

    def get(self, key: str) -> Any | None:
        try:
            v = self.r.get(self.prefix + key)
        except Exception as e:  # a cache outage must never fail a request
            log.warning("redis get failed: %s", e)
            return None
        return None if v is None else json.loads(v)

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        try:
            self.r.set(self.prefix + key, json.dumps(value), ex=int(ttl) if ttl else None)
        except Exception as e:
            log.warning("redis set failed: %s", e)

    def delete(self, key: str) -> None:
        try:
            self.r.delete(self.prefix + key)
        except Exception as e:
            log.warning("redis delete failed: %s", e)

    def incr(self, key: str, ttl: float) -> int:
        try:
            p = self.r.pipeline()
            p.incr(self.prefix + key)
            p.expire(self.prefix + key, int(ttl), nx=True)
            return int(p.execute()[0])
        except Exception as e:
            log.warning("redis incr failed: %s", e)
            return 0

    def ping(self) -> bool:
        try:
            return bool(self.r.ping())
        except Exception:
            return False


def make_cache(url: str):
    if not url:
        return MemoryCache()
    try:
        c = RedisCache(url)
        if c.ping():
            return c
        log.warning("redis at %s not reachable, using in-memory cache", url)
    except Exception as e:
        log.warning("redis unavailable (%s), using in-memory cache", e)
    return MemoryCache()
