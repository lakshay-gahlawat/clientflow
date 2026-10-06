"""
Application settings, loaded from environment variables.
No secrets are hardcoded here — see .env.example for the required keys.
"""
import json

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "ClientFlow"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_postgres_url(cls, value: str) -> str:
        # Render (and some other hosts) issue postgres://; SQLAlchemy 2 wants postgresql://
        if isinstance(value, str) and value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://") :]
        return value

    # Redis / Celery
    REDIS_URL: str

    # Auth
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    # CORS - read as a plain string, then turned into a list by the property below
    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "ALLOWED_ORIGINS"),
    )

    @property
    def CORS_ORIGINS(self) -> list[str]:
        text = self.CORS_ORIGINS_RAW.strip()
        items = json.loads(text) if text.startswith("[") else text.split(",")
        return [o.strip().rstrip("/") for o in items if o.strip()]

    # Stripe (filled in during Phase 8)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_PRO: str = ""

    # Email (filled in during Phase 7)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@clientflow.dev"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
