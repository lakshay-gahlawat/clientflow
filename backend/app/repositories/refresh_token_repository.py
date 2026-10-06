from typing import Optional

from sqlalchemy.orm import Session

from app.models import RefreshToken


def create(db: Session, *, user_id, token_hash: str, csrf_token: str, expires_at) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id, token_hash=token_hash, csrf_token=csrf_token,
        expires_at=expires_at, revoked=False,
    )
    db.add(token)
    db.flush()
    return token


def get_by_hash(db: Session, token_hash: str) -> Optional[RefreshToken]:
    return db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()


def revoke(db: Session, refresh_token: RefreshToken) -> None:
    refresh_token.revoked = True
    db.flush()


def revoke_all_for_user(db: Session, user_id) -> None:
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
    ).update({"revoked": True})
    db.flush()
