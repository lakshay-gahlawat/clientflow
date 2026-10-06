import uuid
from typing import List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPKMixin, CreatedAtMixin


class User(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Workspaces this user owns outright (see Workspace.owner_id).
    owned_workspaces: Mapped[List["Workspace"]] = relationship(
        back_populates="owner", foreign_keys="Workspace.owner_id"
    )

    # Workspace memberships (many-to-many via WorkspaceMember).
    memberships: Mapped[List["WorkspaceMember"]] = relationship(back_populates="user")

    assigned_leads: Mapped[List["Lead"]] = relationship(back_populates="assignee")
    assigned_follow_ups: Mapped[List["FollowUp"]] = relationship(back_populates="assignee")
