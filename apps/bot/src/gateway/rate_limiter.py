import time
from collections import defaultdict, deque

from src.config import get_config


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[int, deque] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        window_start = time.time() - 60
        hits = self._hits[user_id]
        self._cleanup_old_entries(user_id, window_start)
        if len(hits) >= get_config().rate_limit.max_queries_per_user_per_minute:
            return False
        hits.append(time.time())
        return True

    def _cleanup_old_entries(self, user_id: int, window_start: float) -> None:
        hits = self._hits[user_id]
        while hits and hits[0] < window_start:
            hits.popleft()


_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _limiter
