"""
Auth flow tests: registration, login, JWT access tokens, refresh-token
rotation, CSRF protection on the cookie-based refresh flow, and logout.

Split into two layers:
  - Service-level tests (`db` fixture) for the token/session logic itself.
  - API-level tests (`client` fixture) that exercise the real HTTP
    endpoints, including actual Set-Cookie/cookie-jar behavior — this is
    the only way to prove the httpOnly/CSRF wiring genuinely works end
    to end, not just that the underlying functions do.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.core import security
from app.models import User
from app.repositories import refresh_token_repository, user_repository
from app.services import auth_service


# ---------------------------------------------------------------------------
# Service-level: password hashing, JWT, session issuance/rotation
# ---------------------------------------------------------------------------

def test_password_hash_and_verify_roundtrip():
    hashed = security.hash_password("correct-horse-battery-staple")
    assert hashed != "correct-horse-battery-staple"
    assert security.verify_password("correct-horse-battery-staple", hashed)
    assert not security.verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    user_id = "12345678-1234-5678-1234-567812345678"
    token = security.create_access_token(user_id)
    payload = security.decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["type"] == "access"


def test_expired_access_token_rejected():
    import uuid as uuid_module
    from jose import jwt as jose_jwt
    from app.core.config import settings

    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(uuid_module.uuid4()), "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=15), "type": "access",
    }
    expired_token = jose_jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(ValueError):
        security.decode_access_token(expired_token)


def test_register_rejects_duplicate_email(db):
    auth_service.register_user(db, email="dup@test.com", password="password123", full_name="First")
    with pytest.raises(Exception):
        auth_service.register_user(db, email="dup@test.com", password="password123", full_name="Second")


def test_authenticate_rejects_wrong_password(db):
    auth_service.register_user(db, email="wrongpw@test.com", password="correctpassword", full_name="U")
    with pytest.raises(Exception):
        auth_service.authenticate_user(db, email="wrongpw@test.com", password="incorrectpassword")


def test_issue_session_creates_hashed_refresh_token(db):
    user = auth_service.register_user(db, email="session1@test.com", password="password123", full_name="U")
    access_token, raw_refresh, csrf_token = auth_service.issue_session(db, user)

    assert access_token and raw_refresh and csrf_token
    stored = refresh_token_repository.get_by_hash(db, security.hash_token(raw_refresh))
    assert stored is not None
    assert stored.revoked is False
    # The raw token is never the same string as what's stored.
    assert stored.token_hash != raw_refresh


def test_rotate_session_issues_new_tokens_and_revokes_old(db):
    user = auth_service.register_user(db, email="rotate1@test.com", password="password123", full_name="U")
    _, raw_refresh, csrf_token = auth_service.issue_session(db, user)

    new_access, new_refresh, new_csrf, refreshed_user = auth_service.rotate_session(
        db, raw_refresh_token=raw_refresh, csrf_header=csrf_token
    )

    assert refreshed_user.id == user.id
    assert new_refresh != raw_refresh
    old_stored = refresh_token_repository.get_by_hash(db, security.hash_token(raw_refresh))
    assert old_stored.revoked is True


def test_rotate_session_rejects_wrong_csrf_token(db):
    from fastapi import HTTPException

    user = auth_service.register_user(db, email="csrf1@test.com", password="password123", full_name="U")
    _, raw_refresh, _real_csrf = auth_service.issue_session(db, user)

    with pytest.raises(HTTPException) as exc_info:
        auth_service.rotate_session(db, raw_refresh_token=raw_refresh, csrf_header="wrong-csrf-value")
    assert exc_info.value.status_code == 403


def test_reusing_revoked_refresh_token_revokes_all_sessions(db):
    from fastapi import HTTPException

    user = auth_service.register_user(db, email="reuse1@test.com", password="password123", full_name="U")
    _, raw_refresh_1, csrf_1 = auth_service.issue_session(db, user)

    # Rotate once (this revokes raw_refresh_1 and issues a second token).
    _, raw_refresh_2, csrf_2, _ = auth_service.rotate_session(
        db, raw_refresh_token=raw_refresh_1, csrf_header=csrf_1
    )

    # Now replay the FIRST (already-revoked) token — simulates a stolen
    # cookie being used after the legitimate client already rotated past it.
    with pytest.raises(HTTPException):
        auth_service.rotate_session(db, raw_refresh_token=raw_refresh_1, csrf_header=csrf_1)

    # The reuse-detection response should have revoked the SECOND
    # (currently valid) token too — the legitimate session is also killed.
    stored_2 = refresh_token_repository.get_by_hash(db, security.hash_token(raw_refresh_2))
    assert stored_2.revoked is True


def test_revoke_session_marks_token_revoked(db):
    user = auth_service.register_user(db, email="revoke1@test.com", password="password123", full_name="U")
    _, raw_refresh, _ = auth_service.issue_session(db, user)

    auth_service.revoke_session(db, raw_refresh)
    stored = refresh_token_repository.get_by_hash(db, security.hash_token(raw_refresh))
    assert stored.revoked is True


# ---------------------------------------------------------------------------
# API-level: real HTTP requests, real cookies
# ---------------------------------------------------------------------------

def test_register_sets_httponly_refresh_cookie_and_readable_csrf_cookie(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "api1@test.com", "password": "password123", "full_name": "API User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["user"]["email"] == "api1@test.com"

    set_cookies = resp.headers.get_list("set-cookie")
    refresh_cookie = next((v for v in set_cookies if v.startswith("refresh_token=")), "")
    csrf_cookie = next((v for v in set_cookies if v.startswith("csrf_token=")), "")
    assert "HttpOnly" in refresh_cookie
    assert "Path=/api/v1/auth" in refresh_cookie
    assert "HttpOnly" not in csrf_cookie
    # CSRF must be Path=/ so document.cookie on the SPA (e.g. /dashboard)
    # can read it and send X-CSRF-Token on /auth/refresh after a reload.
    assert "Path=/" in csrf_cookie
    assert "Path=/api/v1/auth" not in csrf_cookie


def test_me_requires_bearer_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_succeeds_with_valid_access_token(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "api2@test.com", "password": "password123", "full_name": "API User 2"},
    )
    access_token = reg.json()["access_token"]

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "api2@test.com"


def test_login_wrong_password_returns_401(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "api3@test.com", "password": "correctpassword", "full_name": "U"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": "api3@test.com", "password": "wrongpassword"})
    assert resp.status_code == 401


def test_refresh_flow_without_csrf_header_is_rejected(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "api4@test.com", "password": "password123", "full_name": "U"},
    )
    # TestClient's cookie jar automatically carries the refresh_token
    # cookie set by /register into this call — but we deliberately don't
    # send X-CSRF-Token.
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 403


def test_full_refresh_flow_with_correct_csrf_header_succeeds(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "api5@test.com", "password": "password123", "full_name": "U"},
    )
    old_refresh_cookie = client.cookies.get("refresh_token")
    csrf_cookie_value = client.cookies.get("csrf_token")
    assert csrf_cookie_value is not None

    resp = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_cookie_value})
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "api5@test.com"
    assert "access_token" in resp.json()
    # The refresh token itself rotates — this is the actual rotation
    # guarantee (access-token byte-equality isn't: two tokens minted for
    # the same user in the same second are legitimately identical JWTs,
    # since iat/exp are second-resolution — that's not a bug).
    new_refresh_cookie = client.cookies.get("refresh_token")
    assert new_refresh_cookie != old_refresh_cookie


def test_logout_clears_cookies_and_revokes_refresh_token(client, db):
    client.post(
        "/api/v1/auth/register",
        json={"email": "api6@test.com", "password": "password123", "full_name": "U"},
    )
    raw_refresh_before = client.cookies.get("refresh_token")

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    stored = refresh_token_repository.get_by_hash(db, security.hash_token(raw_refresh_before))
    assert stored.revoked is True

    # Cookie should now be cleared/expired in the jar.
    csrf_header = client.cookies.get("csrf_token")
    refresh_retry = client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf_header or ""})
    assert refresh_retry.status_code == 401
