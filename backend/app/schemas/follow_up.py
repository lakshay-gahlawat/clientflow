import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import FollowUpStatus


class FollowUpCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    due_at: datetime
    # If omitted, defaults to the creator (see service layer) — this
    # matters for the MEMBER-can-only-touch-their-own-follow-ups rule.
    assigned_to: Optional[uuid.UUID] = None


class FollowUpUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    due_at: Optional[datetime] = None
    assigned_to: Optional[uuid.UUID] = None


class FollowUpStatusUpdate(BaseModel):
    status: FollowUpStatus


class FollowUpRead(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    workspace_id: uuid.UUID
    assigned_to: Optional[uuid.UUID]
    title: str
    due_at: datetime
    status: FollowUpStatus
    created_at: datetime

    model_config = {"from_attributes": True}
