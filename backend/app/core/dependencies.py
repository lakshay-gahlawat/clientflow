"""
Shared FastAPI dependencies: authenticated-user resolution and
workspace-scoped authorization (membership + role checks).
"""
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models import User, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories import user_repository, workspace_repository

# auto_error=False so a missing header produces our own 401 message
# rather than FastAPI's generic "Not authenticated" with no detail.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = security.decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = user_repository.get_by_id(db, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


def require_workspace_member(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceMember:
    membership = workspace_repository.get_membership(db, workspace_id, current_user.id)
    if membership is None:
        # 404, not 403 — a non-member gets the same response whether the
        # workspace exists or not, so membership can't be probed for.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return membership


def require_workspace_role(*allowed_roles: WorkspaceRole):
    """
    Dependency factory: require_workspace_role(WorkspaceRole.OWNER) or
    require_workspace_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN).
    Membership is already confirmed (404 case handled) by the time this
    runs; an insufficient role gets 403, since existence isn't in
    question at that point — the user IS a member, just not one with
    enough permission.
    """

    def dependency(membership: WorkspaceMember = Depends(require_workspace_member)) -> WorkspaceMember:
        if membership.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return membership

    return dependency
