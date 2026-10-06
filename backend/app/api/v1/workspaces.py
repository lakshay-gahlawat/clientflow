import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_workspace_member, require_workspace_role
from app.db.session import get_db
from app.models import User, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories import workspace_repository
from app.schemas.workspace import MemberAdd, MemberRead, MemberRoleUpdate, WorkspaceCreate, WorkspaceRead
from app.services import workspace_service

router = APIRouter()


def _member_to_read(member: WorkspaceMember) -> MemberRead:
    return MemberRead(
        id=member.id,
        user_id=member.user_id,
        email=member.user.email,
        full_name=member.user.full_name,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.get("", response_model=list[WorkspaceRead])
def list_my_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspaces = workspace_repository.list_for_user(db, current_user.id)
    return [WorkspaceRead.model_validate(w) for w in workspaces]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = workspace_service.create_workspace(db, name=payload.name, slug=payload.slug, owner=current_user)
    return WorkspaceRead.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    workspace = workspace_repository.get_by_id(db, workspace_id)
    return WorkspaceRead.model_validate(workspace)


@router.get("/{workspace_id}/members", response_model=list[MemberRead])
def list_members(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    members = workspace_repository.list_members(db, workspace_id)
    return [_member_to_read(m) for m in members]


@router.post("/{workspace_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def add_member(
    workspace_id: uuid.UUID,
    payload: MemberAdd,
    # OWNER + ADMIN can manage the team; MEMBER cannot — per the Phase 1
    # permission matrix.
    membership: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)),
    db: Session = Depends(get_db),
):
    member = workspace_service.add_member(db, workspace_id=workspace_id, email=payload.email, role=payload.role)
    return _member_to_read(member)


@router.patch("/{workspace_id}/members/{member_id}", response_model=MemberRead)
def update_member_role(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberRoleUpdate,
    # Role changes are OWNER-only — an ADMIN managing "team operations"
    # (Phase 1) does not include granting/revoking ADMIN itself.
    membership: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OWNER)),
    db: Session = Depends(get_db),
):
    member = workspace_service.update_member_role(
        db, workspace_id=workspace_id, member_id=member_id, new_role=payload.role
    )
    return _member_to_read(member)


@router.delete("/{workspace_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    membership: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)),
    db: Session = Depends(get_db),
):
    workspace_service.remove_member(db, workspace_id=workspace_id, member_id=member_id)
