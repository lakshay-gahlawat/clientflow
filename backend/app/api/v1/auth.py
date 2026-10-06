from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models import User
from app.schemas.auth import AccessTokenResponse, LoginRequest, RegisterRequest, UserRead
from app.services import auth_service

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"
# The refresh token is only sent to auth endpoints (login/refresh/logout).
# Keeping it off the rest of the API reduces how often the browser attaches
# the long-lived credential.
REFRESH_COOKIE_PATH = "/api/v1/auth"
# The CSRF cookie is NOT httpOnly so the SPA can echo it as X-CSRF-Token.
# document.cookie is filtered by the *page* path (e.g. /dashboard), not
# the API path. Path=/ is required for session restore after a refresh;
# Path=/api/v1/auth made the cookie invisible to JS and every
# /auth/refresh from the SPA failed CSRF (403 → login screen).
CSRF_COOKIE_PATH = "/"


def _set_session_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    # Secure cookies are gated on an explicit "production" allowlist, not
    # a "development" blacklist. The blacklist form was a real bug: it
    # marked ANY non-"development" environment (including "test") as
    # secure=True, which breaks cookie delivery over plain HTTP test
    # requests — TestClient (and any real browser) correctly refuses to
    # send a Secure cookie back over http://. Caught by properly wiring
    # up .env.test instead of reusing dev .env for tests.
    is_prod = settings.ENVIRONMENT == "production"

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=max_age,
    )
    # Deliberately NOT httpOnly — the frontend must be able to read this
    # and echo it back as the X-CSRF-Token header (double-submit pattern).
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=is_prod,
        samesite="lax",
        path=CSRF_COOKIE_PATH,
        max_age=max_age,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path=CSRF_COOKIE_PATH)


@router.post("/register", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    _rl=Depends(rate_limit(key_prefix="register", max_requests=10, window_seconds=3600)),
):
    user = auth_service.register_user(
        db, email=payload.email, password=payload.password, full_name=payload.full_name
    )
    access_token, refresh_token, csrf_token = auth_service.issue_session(db, user)
    _set_session_cookies(response, refresh_token, csrf_token)
    return AccessTokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    _rl=Depends(rate_limit(key_prefix="login", max_requests=10, window_seconds=60)),
):
    user = auth_service.authenticate_user(db, email=payload.email, password=payload.password)
    access_token, refresh_token, csrf_token = auth_service.issue_session(db, user)
    _set_session_cookies(response, refresh_token, csrf_token)
    return AccessTokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    csrf_header = request.headers.get("X-CSRF-Token")
    access_token, new_refresh, new_csrf, user = auth_service.rotate_session(
        db, raw_refresh_token=raw_refresh, csrf_header=csrf_header
    )
    _set_session_cookies(response, new_refresh, new_csrf)
    return AccessTokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        auth_service.revoke_session(db, raw_refresh)
    _clear_session_cookies(response)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)
