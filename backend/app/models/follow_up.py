import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, ForeignKeyConstraint, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FollowUpStatus
from app.models.mixins import UUIDPKMixin, CreatedAtMixin


class FollowUp(UUIDPKMixin, CreatedAtMixin, Base):
    __tablename__ = "follow_ups"
    __table_args__ = (
        # This is the index Celery Beat's due-reminder scan actually needs:
        # WHERE status = 'PENDING' AND due_at <= now(). Without it that
        # query degrades to a full table scan as follow-ups accumulate.
        Index("ix_follow_ups_status_due_at", "status", "due_at"),
        # THE core fix: without this, workspace_id on a follow-up is just an
        # independent column that happens to usually match its lead's
        # workspace — nothing stops it from pointing elsewhere. This
        # composite FK forces (lead_id, workspace_id) to match an actual
        # (id, workspace_id) pair on `leads`, so a follow-up can no longer
        # reference a lead belonging to a different workspace, full stop,
        # at the database level.
        ForeignKeyConstraint(
            ["lead_id", "workspace_id"],
            ["leads.id", "leads.workspace_id"],
            name="fk_follow_ups_lead_matches_workspace",
        ),
        # Same workspace-membership guard as on Lead.assigned_to — see that
        # model for the reasoning on why this is NO ACTION, not SET NULL.
        ForeignKeyConstraint(
            ["workspace_id", "assigned_to"],
            ["workspace_members.workspace_id", "workspace_members.user_id"],
            name="fk_follow_ups_assignee_is_workspace_member",
        ),
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized from Lead.workspace_id (see Phase 1 ERD notes) so
    # tenant-scoped queries and indexes don't need a join through Lead.
    # Consistency with the lead's actual workspace is now guaranteed by the
    # composite FK above, not just by application code setting it correctly.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[FollowUpStatus] = mapped_column(
        SAEnum(FollowUpStatus, name="follow_up_status"), nullable=False, default=FollowUpStatus.PENDING
    )
    # Set atomically by the claiming worker (Phase 2 design) — also useful
    # to detect stuck PROCESSING rows if a worker dies mid-send.
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="follow_ups", foreign_keys=[lead_id])
    assignee: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_follow_ups", foreign_keys=[assigned_to]
    )
