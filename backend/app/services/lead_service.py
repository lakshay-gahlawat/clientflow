"""
Lead management business logic. Tenant isolation is enforced at the
repository layer (every query scoped by workspace_id) and backstopped by
the Phase 3 DB constraints; this layer's job is orchestration and turning
constraint violations into clean HTTP errors.
"""
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Lead
from app.models.enums import LeadStatus
from app.repositories import lead_repository, workspace_repository


def _validate_assignee(db: Session, *, workspace_id: uuid.UUID, assigned_to: Optional[uuid.UUID]) -> None:
    if assigned_to is None:
        return
    if workspace_repository.get_membership(db, workspace_id, assigned_to) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_to must be a member of this workspace",
        )


def create_lead(db: Session, *, workspace_id: uuid.UUID, data: dict) -> Lead:
    _validate_assignee(db, workspace_id=workspace_id, assigned_to=data.get("assigned_to"))
    lead = lead_repository.create(db, workspace_id=workspace_id, **data)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Belt-and-suspenders: the pre-check above already validates this,
        # but the DB constraint is the actual source of truth under
        # concurrent modification (e.g. membership removed mid-request).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_to must be a member of this workspace",
        )
    db.refresh(lead)
    return lead


def get_lead(db: Session, *, workspace_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    lead = lead_repository.get_by_id(db, workspace_id=workspace_id, lead_id=lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


def list_leads(db: Session, *, workspace_id: uuid.UUID, **filters):
    return lead_repository.list_paginated(db, workspace_id=workspace_id, **filters)


def update_lead(db: Session, *, workspace_id: uuid.UUID, lead_id: uuid.UUID, data: dict) -> Lead:
    lead = get_lead(db, workspace_id=workspace_id, lead_id=lead_id)
    if "assigned_to" in data:
        _validate_assignee(db, workspace_id=workspace_id, assigned_to=data["assigned_to"])

    for field, value in data.items():
        setattr(lead, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_to must be a member of this workspace",
        )
    db.refresh(lead)
    return lead


def update_status(db: Session, *, workspace_id: uuid.UUID, lead_id: uuid.UUID, new_status: LeadStatus) -> Lead:
    lead = get_lead(db, workspace_id=workspace_id, lead_id=lead_id)
    lead.status = new_status
    db.commit()
    db.refresh(lead)
    return lead


def delete_lead(db: Session, *, workspace_id: uuid.UUID, lead_id: uuid.UUID) -> None:
    lead = get_lead(db, workspace_id=workspace_id, lead_id=lead_id)
    lead_repository.delete(db, lead)
    db.commit()
