"""
Password hashing, JWT access tokens, and refresh/CSRF token utilities.

Password hashing uses `bcrypt` directly rather than passlib's bcrypt
wrapper — passlib's version-detection code is broken against bcrypt>=4.1
(it reads a `__about__` attribute bcrypt no longer exposes), confirmed
during Phase 4 implementation. Using bcrypt directly avoids the dependency
entirely rather than pinning to an old bcrypt version.
"""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt silently truncates/errors past 72 bytes — enforced at the schema
# layer too (RegisterRequest.password max_length), but guarded here as
# well since this function shouldn't trust its caller blindly.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password must be 72 bytes or fewer")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash, mismatched byte length, etc. — never a match.
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "iat": now, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise ValueError("Wrong token type")
    return payload


def generate_opaque_token() -> str:
    """Used for both refresh tokens and CSRF tokens — high-entropy, URL-safe."""
    return secrets.token_urlsafe(48)


def hash_token(raw_token: str) -> str:
    """
    Refresh tokens are stored hashed (never plaintext) so a DB read alone
    can't be replayed as a valid session — same principle as password
    hashing, applied to bearer secrets. SHA-256 (not bcrypt) is correct
    here: this token is already high-entropy random data, not a
    low-entropy human password, so there's nothing for bcrypt's
    slow-hashing to protect against — a fast, deterministic hash is what
    we actually want for a fast indexed lookup.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    """Timing-safe comparison for the CSRF double-submit check."""
    return hmac.compare_digest(a, b)
