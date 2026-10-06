"""
ClientFlow API entrypoint.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,  # required for the httpOnly refresh cookie
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Baseline HTTP security headers, applied to every response.
    Deliberately NOT including Content-Security-Policy here — the
    default /docs (Swagger UI) loads its JS/CSS from a CDN, and a
    correct CSP needs to be scoped around that deliberately rather than
    guessed at as a side effect of this fix. Add one separately if /docs
    is disabled or CSP is specifically scoped for it.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT != "development":
        # Only meaningful over HTTPS — harmless but pointless over plain
        # HTTP, so scoped to non-dev the same way the cookie Secure flag is.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
