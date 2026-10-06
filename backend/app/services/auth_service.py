"""
Registration, login, and refresh-token session lifecycle.

Session tuple convention: functions that issue tokens return
(access_token, raw_refresh_token, csrf_token[, user]) — the raw refresh
token only ever exists in memory here and in the outgoing Set-Cookie
header; it is never logged and never persisted (only its hash is).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models import User
from app.repositories import refresh_token_repository, user_repository


def register_user(db: Session, *, email: str, password: str, full_name: str) -> User:
    if user_repository.get_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    hashed = security.hash_password(password)
    user = user_repository.create(db, email=email, hashed_password=hashed, full_name=full_name)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User:
    user = user_repository.get_by_email(db, email)
    # Same error for "no such user" and "wrong password" — don't leak
    # which one it was to an attacker probing for valid emails.
    if not user or not security.verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return user


def _issue_tokens_for_user(db: Session, user: User) -> Tuple[str, str, str]:
    access_token = security.create_access_token(user.id)
    raw_refresh = security.generate_opaque_token()
    csrf_token = security.generate_opaque_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token_repository.create(
        db,
        user_id=user.id,
        token_hash=security.hash_token(raw_refresh),
        csrf_token=csrf_token,
        expires_at=expires_at,
    )
    return access_token, raw_refresh, csrf_token


def issue_session(db: Session, user: User) -> Tuple[str, str, str]:
    """Called on register/login. Commits the new refresh-token row."""
    tokens = _issue_tokens_for_user(db, user)
    db.commit()
    return tokens


def rotate_session(db: Session, *, raw_refresh_token: str, csrf_header: str) -> Tuple[str, str, str, User]:
    """
    Called on /auth/refresh. Validates the presented refresh token +
    CSRF header, revokes the old token, issues a new pair (rotation).
    """
    token_hash = security.hash_token(raw_refresh_token)
    stored = refresh_token_repository.get_by_hash(db, token_hash)

    if stored is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if stored.revoked:
        # Reuse of an already-rotated token is a theft/replay signal —
        # kill every session for this user, not just this one.
        refresh_token_repository.revoke_all_for_user(db, stored.user_id)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    if not csrf_header or not security.constant_time_compare(csrf_header, stored.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")

    user = user_repository.get_by_id(db, stored.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    refresh_token_repository.revoke(db, stored)
    access_token, new_raw_refresh, new_csrf = _issue_tokens_for_user(db, user)
    db.commit()
    return access_token, new_raw_refresh, new_csrf, user


def revoke_session(db: Session, raw_refresh_token: str) -> None:
    """Called on /auth/logout. Silently no-ops on an already-invalid token."""
    token_hash = security.hash_token(raw_refresh_token)
    stored = refresh_token_repository.get_by_hash(db, token_hash)
    if stored and not stored.revoked:
        refresh_token_repository.revoke(db, stored)
        db.commit()
