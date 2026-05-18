"""
轻量 TTL 缓存。

Redis 后续可以接在这一层下面；MVP 阶段先用进程内缓存，保证本地开发
不依赖额外服务也能工作。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheItem:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self):
        self._items: dict[str, CacheItem] = {}

    def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None
        if item.expires_at <= time.time():
            self._items.pop(key, None)
            return None
        return item.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._items[key] = CacheItem(
            value=value,
            expires_at=time.time() + ttl_seconds,
        )

    def delete(self, key: str) -> None:
        self._items.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        for key in list(self._items):
            if key.startswith(prefix):
                self._items.pop(key, None)


cache = TTLCache()
