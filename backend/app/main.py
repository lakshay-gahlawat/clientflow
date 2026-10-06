"""
ClientFlow API entrypoint.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(title=settings.PROJECT_NAME)

# 1. Custom Security Headers Middleware (Added FIRST so CORS runs before it)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    # Pass preflight OPTIONS requests directly through without interception
    if request.method == "OPTIONS":
        return await call_next(request)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.ENVIRONMENT != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# 2. Parse CORS Origins safely to ensure it is always a List[str]
if isinstance(settings.CORS_ORIGINS, str):
    cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
else:
    cors_origins = settings.CORS_ORIGINS

# 3. CORS Middleware (Added LAST so it wraps all requests FIRST)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,  # required for the httpOnly refresh cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}