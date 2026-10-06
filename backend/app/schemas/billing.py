import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import SubscriptionPlan, SubscriptionStatus


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class SubscriptionRead(BaseModel):
    workspace_id: uuid.UUID
    plan: SubscriptionPlan
    status: SubscriptionStatus
    current_period_end: Optional[datetime]

    model_config = {"from_attributes": True}
