import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_workspace_member, require_workspace_role
from app.db.session import get_db
from app.models import WorkspaceMember
from app.models.enums import LeadStatus, WorkspaceRole
from app.schemas.lead import LeadCreate, LeadRead, LeadStatusUpdate, LeadUpdate, PaginatedLeads
from app.services import lead_service

router = APIRouter()

# Create/read/update/status-change/assign are open to every workspace
# role (OWNER/ADMIN/MEMBER) — day-to-day CRM work. Delete is restricted
# below to OWNER/ADMIN only, as a more destructive, "manage" action.
_ANY_MEMBER = require_workspace_member
_CAN_DELETE = require_workspace_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    workspace_id: uuid.UUID,
    payload: LeadCreate,
    membership: WorkspaceMember = Depends(_ANY_MEMBER),
    db: Session = Depends(get_db),
):
    lead = lead_service.create_lead(db, workspace_id=workspace_id, data=payload.model_dump())
    return LeadRead.model_validate(lead)


@router.get("", response_model=PaginatedLeads)
def list_leads(
    workspace_id: uuid.UUID,
    status_filter: Optional[LeadStatus] = Query(default=None, alias="status"),
    assigned_to: Optional[uuid.UUID] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=255),
    sort_by: str = Query(default="created_at", pattern="^(created_at|updated_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    membership: WorkspaceMember = Depends(_ANY_MEMBER),
    db: Session = Depends(get_db),
):
    items, total = lead_service.list_leads(
        db,
        workspace_id=workspace_id,
        status=status_filter,
        assigned_to=assigned_to,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return PaginatedLeads(
        items=[LeadRead.model_validate(lead) for lead in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{lead_id}", response_model=LeadRead)
def get_lead(
    workspace_id: uuid.UUID,
    lead_id: uuid.UUID,
    membership: WorkspaceMember = Depends(_ANY_MEMBER),
    db: Session = Depends(get_db),
):
    lead = lead_service.get_lead(db, workspace_id=workspace_id, lead_id=lead_id)
    return LeadRead.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadRead)
def update_lead(
    workspace_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadUpdate,
    membership: WorkspaceMember = Depends(_ANY_MEMBER),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    lead = lead_service.update_lead(db, workspace_id=workspace_id, lead_id=lead_id, data=data)
    return LeadRead.model_validate(lead)


@router.patch("/{lead_id}/status", response_model=LeadRead)
def update_lead_status(
    workspace_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadStatusUpdate,
    membership: WorkspaceMember = Depends(_ANY_MEMBER),
    db: Session = Depends(get_db),
):
    lead = lead_service.update_status(db, workspace_id=workspace_id, lead_id=lead_id, new_status=payload.status)
    return LeadRead.model_validate(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(
    workspace_id: uuid.UUID,
    lead_id: uuid.UUID,
    membership: WorkspaceMember = Depends(_CAN_DELETE),
    db: Session = Depends(get_db),
):
    lead_service.delete_lead(db, workspace_id=workspace_id, lead_id=lead_id)
