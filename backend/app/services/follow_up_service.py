"""
Follow-up business logic and authorization.

Permission model (from the original product spec, section 6):
  OWNER / ADMIN — full control over every follow-up in the workspace.
  MEMBER        — can create follow-ups (assigned to themselves by
                   default) and manage only the ones assigned to them.
                   This is stricter than Lead permissions (where any
                   member can touch any lead) — follow-ups are personal
                   task lists, leads are shared workspace data.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import FollowUp, Lead, User, WorkspaceMember
from app.models.enums import FollowUpStatus, WorkspaceRole
from app.repositories import follow_up_repository, lead_repository, workspace_repository


def _is_manager(membership: WorkspaceMember) -> bool:
    return membership.role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


def _validate_assignee(db: Session, *, workspace_id: uuid.UUID, assigned_to: Optional[uuid.UUID]) -> None:
    if assigned_to is None:
        return
    if workspace_repository.get_membership(db, workspace_id, assigned_to) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_to must be a member of this workspace",
        )


def create_follow_up(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    lead_id: uuid.UUID,
    actor: User,
    membership: WorkspaceMember,
    title: str,
    due_at: datetime,
    assigned_to: Optional[uuid.UUID],
) -> FollowUp:
    lead = lead_repository.get_by_id(db, workspace_id=workspace_id, lead_id=lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    resolved_assignee = assigned_to if assigned_to is not None else actor.id
    if not _is_manager(membership) and resolved_assignee != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Members can only create follow-ups assigned to themselves",
        )
    _validate_assignee(db, workspace_id=workspace_id, assigned_to=resolved_assignee)

    follow_up = follow_up_repository.create(
        db,
        lead_id=lead_id,
        workspace_id=workspace_id,
        title=title,
        due_at=due_at,
        assigned_to=resolved_assignee,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_to must be a member of this workspace",
        )
    db.refresh(follow_up)
    return follow_up


def get_follow_up(db: Session, *, workspace_id: uuid.UUID, follow_up_id: uuid.UUID) -> FollowUp:
    follow_up = follow_up_repository.get_by_id(db, workspace_id=workspace_id, follow_up_id=follow_up_id)
    if follow_up is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")
    return follow_up


def _check_can_modify(follow_up: FollowUp, actor: User, membership: WorkspaceMember) -> None:
    if not _is_manager(membership) and follow_up.assigned_to != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage follow-ups assigned to you",
        )


def list_follow_ups(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    status: Optional[FollowUpStatus] = None,
    assigned_to: Optional[uuid.UUID] = None,
    lead_id: Optional[uuid.UUID] = None,
) -> list[FollowUp]:
    return follow_up_repository.list_for_workspace(
        db, workspace_id=workspace_id, status=status, assigned_to=assigned_to, lead_id=lead_id
    )


def update_follow_up(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    actor: User,
    membership: WorkspaceMember,
    data: dict,
) -> FollowUp:
    follow_up = get_follow_up(db, workspace_id=workspace_id, follow_up_id=follow_up_id)
    _check_can_modify(follow_up, actor, membership)

    if "assigned_to" in data:
        new_assignee = data["assigned_to"]
        if not _is_manager(membership) and new_assignee is not None and new_assignee != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Members can only assign their own follow-ups to themselves",
            )
        _validate_assignee(db, workspace_id=workspace_id, assigned_to=new_assignee)

    for field, value in data.items():
        setattr(follow_up, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_to must be a member of this workspace",
        )
    db.refresh(follow_up)
    return follow_up


def cancel_follow_up(
    db: Session, *, workspace_id: uuid.UUID, follow_up_id: uuid.UUID, actor: User, membership: WorkspaceMember
) -> FollowUp:
    follow_up = get_follow_up(db, workspace_id=workspace_id, follow_up_id=follow_up_id)
    _check_can_modify(follow_up, actor, membership)

    # Only PENDING follow-ups are meaningfully cancellable — one that's
    # already SENT happened, and one mid-send (PROCESSING) is about to.
    if follow_up.status not in (FollowUpStatus.PENDING,):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel a follow-up with status {follow_up.status.value}",
        )
    follow_up.status = FollowUpStatus.CANCELLED
    db.commit()
    db.refresh(follow_up)
    return follow_up


def delete_follow_up(
    db: Session, *, workspace_id: uuid.UUID, follow_up_id: uuid.UUID, actor: User, membership: WorkspaceMember
) -> None:
    follow_up = get_follow_up(db, workspace_id=workspace_id, follow_up_id=follow_up_id)
    _check_can_modify(follow_up, actor, membership)
    follow_up_repository.delete(db, follow_up)
    db.commit()
