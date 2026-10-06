"""
Workspace creation and membership/role management business logic.

Kept intentionally thin — most of the real invariant enforcement here is
actually happening at the database layer (composite FKs from Phase 3,
the workspace_role enum). This layer's job is orchestration (workspace +
owner-membership created atomically) and the handful of rules that
aren't practical to express as DB constraints (e.g. "can't demote the
owner via the role-update endpoint").
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories import subscription_repository, user_repository, workspace_repository


def create_workspace(db: Session, *, name: str, slug: str, owner: User) -> Workspace:
    if workspace_repository.get_by_slug(db, slug):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")

    workspace = workspace_repository.create_workspace(db, name=name, slug=slug, owner_id=owner.id)
    # Creating the workspace without also creating the OWNER membership row
    # would leave the owner unable to pass require_workspace_member on
    # their own workspace — these two writes must happen together.
    workspace_repository.add_member(db, workspace_id=workspace.id, user_id=owner.id, role=WorkspaceRole.OWNER)
    # Every workspace starts on the FREE plan so a Subscription row always
    # exists — the billing page has something real to display from day
    # one, not a "no subscription found" edge case to special-case.
    subscription_repository.create_default(db, workspace_id=workspace.id)
    db.commit()
    db.refresh(workspace)
    return workspace


def add_member(db: Session, *, workspace_id: uuid.UUID, email: str, role: WorkspaceRole) -> WorkspaceMember:
    if role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ownership transfer isn't supported via this endpoint",
        )
    user = user_repository.get_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user with that email")
    if workspace_repository.get_membership(db, workspace_id, user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member")

    member = workspace_repository.add_member(db, workspace_id=workspace_id, user_id=user.id, role=role)
    db.commit()
    db.refresh(member)
    return member


def update_member_role(
    db: Session, *, workspace_id: uuid.UUID, member_id: uuid.UUID, new_role: WorkspaceRole
) -> WorkspaceMember:
    target = workspace_repository.get_member_by_id(db, workspace_id, member_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the owner's role")
    if new_role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ownership transfer isn't supported via this endpoint",
        )

    target.role = new_role
    db.commit()
    db.refresh(target)
    return target


def remove_member(db: Session, *, workspace_id: uuid.UUID, member_id: uuid.UUID) -> None:
    target = workspace_repository.get_member_by_id(db, workspace_id, member_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the workspace owner")

    db.delete(target)
    try:
        db.commit()
    except IntegrityError:
        # The Phase 3 composite FK (leads/follow_ups -> workspace_members)
        # blocks this if the member is still assigned to anything in the
        # workspace. Surfacing it as a clear 409 rather than a raw 500 —
        # this is expected, not a bug, once Leads exist in Phase 5.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member is still assigned to leads or follow-ups in this workspace; reassign first",
        )
