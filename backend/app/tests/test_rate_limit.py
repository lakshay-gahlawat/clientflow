"""
Rate limiter test. Runs with ENVIRONMENT temporarily overridden to
something other than "test" — otherwise the limiter no-ops by design
(see core/rate_limit.py) so the rest of the suite isn't broken by it.

Unlike Postgres (rolled back per-test via the `db` fixture's SAVEPOINT),
Redis state is NOT automatically reset between tests or between full
suite runs — this test must clean up its own rate-limit counter key
first, or a previous run leaves it order/run-dependent.
"""
import redis

from app.core.config import settings


def _clear_rate_limit_keys():
    r = redis.from_url(settings.REDIS_URL, decode_responses=True)
    for key in r.keys("ratelimit:login:*"):
        r.delete(key)


def test_login_is_rate_limited_after_threshold(client, monkeypatch):
    _clear_rate_limit_keys()
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimit_a@test.com", "password": "password123", "full_name": "U"},
    )

    responses = [
        client.post("/api/v1/auth/login", json={"email": "ratelimit_a@test.com", "password": "wrong"})
        for _ in range(12)
    ]
    statuses = [r.status_code for r in responses]

    assert 429 in statuses
    # The limit (10/60s) should kick in before all 12 attempts succeed
    # through to a normal 401 — confirms it's actually throttling, not
    # just present in code but never triggered.
    assert statuses.count(429) >= 1
    assert statuses[:10].count(401) == 10  # first 10 are normal "wrong password" rejections


def test_rate_limiter_is_disabled_in_test_environment_by_default(client):
    # No monkeypatch here — ENVIRONMENT stays "test" (from .env.test),
    # confirming the bypass documented in core/rate_limit.py actually
    # takes effect without needing to override anything.
    responses = [
        client.post("/api/v1/auth/login", json={"email": "nonexistent@test.com", "password": "wrong"})
        for _ in range(15)
    ]
    assert all(r.status_code == 401 for r in responses)
