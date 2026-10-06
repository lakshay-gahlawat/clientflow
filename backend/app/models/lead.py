import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LeadStatus
from app.models.mixins import UUIDPKMixin, CreatedAtMixin


class Lead(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        # Backs the pipeline view / status filters — the query every
        # leads-list request runs is "this workspace, this status".
        Index("ix_leads_workspace_status", "workspace_id", "status"),
        # Lets FollowUp hold a composite FK to (lead_id, workspace_id) so the
        # DB itself rejects a follow-up whose workspace_id doesn't match its
        # lead's actual workspace. `id` is already unique via the PK; this
        # adds the (id, workspace_id) pair as a referenceable unique target.
        UniqueConstraint("id", "workspace_id", name="uq_leads_id_workspace"),
        # Enforces that assigned_to, when set, must be a member of THIS
        # workspace — not just any user in the system. References the
        # existing (workspace_id, user_id) unique constraint on
        # workspace_members. Left as NO ACTION (default) rather than
        # CASCADE/SET NULL: removing a member while they're still assigned
        # to leads should fail loudly (reassign first), not silently null
        # out data.
        ForeignKeyConstraint(
            ["workspace_id", "assigned_to"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            name="fk_leads_assignee_is_workspace_member",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="lead_status"), nullable=False, default=LeadStatus.NEW
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Nullable + SET NULL on this single-column FK: an unassigned lead is
    # valid, and if the USER account itself is deleted entirely, the lead
    # just becomes unassigned rather than blocking the delete. The separate
    # composite FK above (workspace membership) additionally guards against
    # assigning a user who was never added to this workspace.
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="leads", foreign_keys=[workspace_id])
    assignee: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_leads", foreign_keys=[assigned_to]
    )
    follow_ups: Mapped[List["FollowUp"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
        foreign_keys="FollowUp.lead_id",
    )
