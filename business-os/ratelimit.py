import time
import logging
from fastapi import HTTPException
from db import rate_limits_col

log = logging.getLogger("ratelimit")

_MEMORY_BUCKETS: dict[str, list[float]] = {}


# Fixed-window rate limiter backed by DB or memory
class RateLimiter:
    # Configure the window size and request cap
    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    # Reject a request when the key's window is full
    def check(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        if rate_limits_col is not None:
            rate_limits_col.delete_many({"key": key, "ts": {"$lt": cutoff}})
            count = rate_limits_col.count_documents({"key": key, "ts": {"$gte": cutoff}})
            if count >= self.max_requests:
                raise HTTPException(429, "Too many requests. Please slow down.")
            rate_limits_col.insert_one({"key": key, "ts": now})
        else:
            bucket = _MEMORY_BUCKETS.setdefault(key, [])
            bucket[:] = [t for t in bucket if now - t < self.window_seconds]
            if len(bucket) >= self.max_requests:
                raise HTTPException(429, "Too many requests. Please slow down.")
            bucket.append(now)


general_limiter = RateLimiter(max_requests=60, window_seconds=60.0)
strict_limiter = RateLimiter(max_requests=10, window_seconds=60.0)
