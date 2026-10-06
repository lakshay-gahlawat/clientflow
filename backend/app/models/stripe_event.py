import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPKMixin, CreatedAtMixin


class StripeEvent(UUIDPKMixin, CreatedAtMixin, Base):
    """
    Records every Stripe webhook event ID we've successfully processed.
    Stripe explicitly documents that webhooks may be delivered more than
    once (network retries, etc.) — checking this table before applying an
    event's side effects, and recording it after, is what makes webhook
    handling idempotent regardless of whether the underlying state change
    itself happens to be idempotent.
    """
    __tablename__ = "stripe_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
