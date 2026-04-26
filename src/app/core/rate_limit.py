from dataclasses import dataclass, field
from time import monotonic

from fastapi import Request


@dataclass
class RateLimitBucket:
    reset_at: float
    count: int = 0


@dataclass
class InMemoryRateLimiter:
    max_requests: int
    window_seconds: int
    buckets: dict[str, RateLimitBucket] = field(default_factory=dict)

    def is_allowed(self, key: str) -> bool:
        now = monotonic()
        bucket = self.buckets.get(key)
        if bucket is None or bucket.reset_at <= now:
            self.buckets[key] = RateLimitBucket(reset_at=now + self.window_seconds, count=1)
            return True

        if bucket.count >= self.max_requests:
            return False

        bucket.count += 1
        return True


def get_rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{request.url.path}"


def should_skip_rate_limit(request: Request) -> bool:
    return request.method == "OPTIONS" or request.url.path in {"/health", "/v1/health"}
