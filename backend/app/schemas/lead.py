import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import LeadStatus


class LeadCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=50)
    source: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None


class LeadUpdate(BaseModel):
    """All fields optional — PATCH semantics, only supplied fields change."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    company: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=50)
    source: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadRead(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    company: str
    email: str
    phone: Optional[str]
    source: Optional[str]
    status: LeadStatus
    notes: Optional[str]
    assigned_to: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedLeads(BaseModel):
    items: List[LeadRead]
    total: int
    page: int
    page_size: int
