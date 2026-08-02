import time

from fastapi import Request

from app.core.exceptions import AppException
from app.db.redis import redis_client


class RateLimitExceeded(AppException):
    status_code = 429
    error_code = "TOO_MANY_ATTEMPTS"


class RateLimiter:
    """Fixed-window rate limiter backed by Redis.

    Not exact (a fixed window can allow up to ~2x the limit right at a window
    boundary), but that's an acceptable tradeoff for blunting brute-force /
    credential-stuffing attempts on auth endpoints without pulling in a
    dependency like slowapi for one small piece of logic.
    """

    def __init__(self, limit: int, window_seconds: int, scope: str) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.scope = scope

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time()) // self.window_seconds
        key = f"ratelimit:{self.scope}:{client_ip}:{window}"

        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, self.window_seconds)

        if count > self.limit:
            raise RateLimitExceeded("Too many attempts. Try again in a moment.")


# Shared instances. Registration/login get a tight quota since they're the
# classic brute-force/credential-stuffing target; everything else that
# writes gets a wider net that a real user won't bump into in normal use,
# but that still bounds abuse (and, for /interviews/{id}/answer, bounds
# how many real AI-provider calls one IP can trigger per minute).
auth_rate_limit = RateLimiter(limit=5, window_seconds=60, scope="auth")
general_write_rate_limit = RateLimiter(limit=30, window_seconds=60, scope="general_write")
