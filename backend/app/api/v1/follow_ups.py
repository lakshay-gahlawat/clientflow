import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_workspace_member
from app.db.session import get_db
from app.models import User, WorkspaceMember
from app.models.enums import FollowUpStatus
from app.schemas.follow_up import FollowUpCreate, FollowUpRead, FollowUpUpdate
from app.services import follow_up_service

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/leads/{lead_id}/follow-ups",
    response_model=FollowUpRead,
    status_code=status.HTTP_201_CREATED,
    tags=["follow-ups"],
)
def create_follow_up(
    workspace_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: FollowUpCreate,
    current_user: User = Depends(get_current_user),
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    follow_up = follow_up_service.create_follow_up(
        db,
        workspace_id=workspace_id,
        lead_id=lead_id,
        actor=current_user,
        membership=membership,
        title=payload.title,
        due_at=payload.due_at,
        assigned_to=payload.assigned_to,
    )
    return FollowUpRead.model_validate(follow_up)


@router.get(
    "/workspaces/{workspace_id}/follow-ups",
    response_model=list[FollowUpRead],
    tags=["follow-ups"],
)
def list_follow_ups(
    workspace_id: uuid.UUID,
    status_filter: Optional[FollowUpStatus] = Query(default=None, alias="status"),
    lead_id: Optional[uuid.UUID] = Query(default=None),
    mine: bool = Query(default=False, description="If true, only follow-ups assigned to the current user"),
    current_user: User = Depends(get_current_user),
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    follow_ups = follow_up_service.list_follow_ups(
        db,
        workspace_id=workspace_id,
        status=status_filter,
        assigned_to=current_user.id if mine else None,
        lead_id=lead_id,
    )
    return [FollowUpRead.model_validate(f) for f in follow_ups]


@router.patch(
    "/workspaces/{workspace_id}/follow-ups/{follow_up_id}",
    response_model=FollowUpRead,
    tags=["follow-ups"],
)
def update_follow_up(
    workspace_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    payload: FollowUpUpdate,
    current_user: User = Depends(get_current_user),
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    follow_up = follow_up_service.update_follow_up(
        db,
        workspace_id=workspace_id,
        follow_up_id=follow_up_id,
        actor=current_user,
        membership=membership,
        data=data,
    )
    return FollowUpRead.model_validate(follow_up)


@router.post(
    "/workspaces/{workspace_id}/follow-ups/{follow_up_id}/cancel",
    response_model=FollowUpRead,
    tags=["follow-ups"],
)
def cancel_follow_up(
    workspace_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    follow_up = follow_up_service.cancel_follow_up(
        db, workspace_id=workspace_id, follow_up_id=follow_up_id, actor=current_user, membership=membership
    )
    return FollowUpRead.model_validate(follow_up)


@router.delete(
    "/workspaces/{workspace_id}/follow-ups/{follow_up_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["follow-ups"],
)
def delete_follow_up(
    workspace_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    follow_up_service.delete_follow_up(
        db, workspace_id=workspace_id, follow_up_id=follow_up_id, actor=current_user, membership=membership
    )
