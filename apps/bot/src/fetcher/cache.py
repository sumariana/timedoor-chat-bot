import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    data: Any
    expires_at: float


class CacheStore:
    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if time.time() >= entry.expires_at:
            self._entries.pop(key, None)
            return None
        return entry.data

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._entries[key] = _Entry(value, time.time() + ttl)

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)


_cache = CacheStore()


def get_cache() -> CacheStore:
    return _cache
