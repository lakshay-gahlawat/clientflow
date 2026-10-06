from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole


def create_workspace(db: Session, *, name: str, slug: str, owner_id) -> Workspace:
    ws = Workspace(name=name, slug=slug, owner_id=owner_id)
    db.add(ws)
    db.flush()
    return ws


def get_by_id(db: Session, workspace_id) -> Optional[Workspace]:
    return db.get(Workspace, workspace_id)


def list_for_user(db: Session, user_id):
    return (
        db.query(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(WorkspaceMember.user_id == user_id)
        .order_by(Workspace.created_at.asc())
        .all()
    )


def get_by_slug(db: Session, slug: str) -> Optional[Workspace]:
    return db.query(Workspace).filter(Workspace.slug == slug).first()


def get_membership(db: Session, workspace_id, user_id) -> Optional[WorkspaceMember]:
    return (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        .first()
    )


def add_member(db: Session, *, workspace_id, user_id, role: WorkspaceRole) -> WorkspaceMember:
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)
    db.add(member)
    db.flush()
    return member


def list_members(db: Session, workspace_id):
    # joinedload(.user): the audit found this was N+1 — every caller
    # (api/v1/workspaces._member_to_read) accesses member.user.email /
    # member.user.full_name per row, which without this triggers one
    # lazy-load query per member. A single LEFT JOIN fixes it.
    return (
        db.query(WorkspaceMember)
        .options(joinedload(WorkspaceMember.user))
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )


def get_member_by_id(db: Session, workspace_id, member_id) -> Optional[WorkspaceMember]:
    return (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.id == member_id, WorkspaceMember.workspace_id == workspace_id)
        .first()
    )
