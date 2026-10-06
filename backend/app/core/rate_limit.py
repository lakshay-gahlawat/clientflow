"""
Minimal Redis-backed fixed-window rate limiter.

Scoped deliberately to the endpoints where the cost of NOT limiting is
highest — login (credential brute-forcing) and register (spam/abuse) —
rather than blanket middleware across every route. A reverse proxy /
API gateway in front of the real deployment should still apply broader
request-rate limiting; this is defense at the application layer for the
two endpoints that matter most if that outer layer is ever misconfigured
or absent.
"""
import redis

from app.core.config import settings
from fastapi import HTTPException, Request, status

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def rate_limit(*, key_prefix: str, max_requests: int, window_seconds: int):
    """
    Dependency factory. Keyed by client IP — good enough for this scale;
    a shared corporate NAT briefly hitting the ceiling is an acceptable
    tradeoff against the alternative (unlimited login attempts).
    """

    def dependency(request: Request) -> None:
        # Rate limiting is a production/dev concern. The test suite
        # deliberately makes far more than max_requests login/register
        # calls in quick succession (many separate test scenarios), and
        # TestClient reports a fixed client IP for all of them, which
        # would make every test after the first ~10 fail with 429 for
        # reasons unrelated to what that test is actually checking.
        # ENVIRONMENT=test is only ever set by backend/.env.test (see
        # root conftest.py) — never in real dev/prod configuration.
        if settings.ENVIRONMENT == "test":
            return

        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{key_prefix}:{client_ip}"

        try:
            r = _get_redis()
            current = r.incr(key)
            if current == 1:
                r.expire(key, window_seconds)
        except redis.RedisError:
            # Redis being unavailable should not itself take down auth —
            # fail open rather than lock every user out because of an
            # infra blip. Logged so it's visible, not silent.
            import logging

            logging.getLogger(__name__).warning("Rate limiter: Redis unavailable, failing open")
            return

        if current > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

    return dependency
