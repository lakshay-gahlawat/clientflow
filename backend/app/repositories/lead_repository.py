"""
Lead data access. Every function that takes a workspace_id filters on it
unconditionally — this file is the enforcement point for tenant isolation
at the query level (on top of the Phase 3 DB constraints).
"""
import uuid
from typing import Optional, Tuple

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Lead
from app.models.enums import LeadStatus

ALLOWED_SORT_FIELDS = {
    "created_at": Lead.created_at,
    "updated_at": Lead.updated_at,
    "name": Lead.name,
}


def create(db: Session, *, workspace_id: uuid.UUID, **fields) -> Lead:
    lead = Lead(workspace_id=workspace_id, **fields)
    db.add(lead)
    db.flush()
    return lead


def get_by_id(db: Session, *, workspace_id: uuid.UUID, lead_id: uuid.UUID) -> Optional[Lead]:
    # The workspace_id filter here — not just "WHERE id = lead_id" — is
    # what makes a lead ID from a different workspace come back as
    # nothing rather than someone else's data.
    return (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.workspace_id == workspace_id)
        .first()
    )


def _base_query(
    *,
    workspace_id: uuid.UUID,
    status: Optional[LeadStatus],
    assigned_to: Optional[uuid.UUID],
    search: Optional[str],
) -> Select:
    stmt = select(Lead).where(Lead.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(Lead.status == status)
    if assigned_to is not None:
        stmt = stmt.where(Lead.assigned_to == assigned_to)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(Lead.name.ilike(pattern), Lead.company.ilike(pattern), Lead.email.ilike(pattern))
        )
    return stmt


def list_paginated(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    status: Optional[LeadStatus] = None,
    assigned_to: Optional[uuid.UUID] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> Tuple[list, int]:
    base = _base_query(workspace_id=workspace_id, status=status, assigned_to=assigned_to, search=search)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()

    sort_column = ALLOWED_SORT_FIELDS.get(sort_by, Lead.created_at)
    ordered = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    stmt = base.order_by(ordered).offset((page - 1) * page_size).limit(page_size)

    items = db.execute(stmt).scalars().all()
    return items, total


def delete(db: Session, lead: Lead) -> None:
    db.delete(lead)
    db.flush()
