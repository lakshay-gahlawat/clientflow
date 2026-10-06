"""
FollowUp data access. list/get functions filter by workspace_id
unconditionally, same tenant-isolation discipline as lead_repository.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import FollowUp
from app.models.enums import FollowUpStatus


def create(db: Session, *, lead_id: uuid.UUID, workspace_id: uuid.UUID, **fields) -> FollowUp:
    follow_up = FollowUp(lead_id=lead_id, workspace_id=workspace_id, **fields)
    db.add(follow_up)
    db.flush()
    return follow_up


def get_by_id(db: Session, *, workspace_id: uuid.UUID, follow_up_id: uuid.UUID) -> Optional[FollowUp]:
    return (
        db.query(FollowUp)
        .filter(FollowUp.id == follow_up_id, FollowUp.workspace_id == workspace_id)
        .first()
    )


def list_for_workspace(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    status: Optional[FollowUpStatus] = None,
    assigned_to: Optional[uuid.UUID] = None,
    lead_id: Optional[uuid.UUID] = None,
) -> list[FollowUp]:
    stmt = select(FollowUp).where(FollowUp.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(FollowUp.status == status)
    if assigned_to is not None:
        stmt = stmt.where(FollowUp.assigned_to == assigned_to)
    if lead_id is not None:
        stmt = stmt.where(FollowUp.lead_id == lead_id)
    stmt = stmt.order_by(FollowUp.due_at.asc())
    return list(db.execute(stmt).scalars().all())


def delete(db: Session, follow_up: FollowUp) -> None:
    db.delete(follow_up)
    db.flush()


# --- Worker-side operations (used by Celery tasks, not the API) ----------

def find_due_pending_ids(db: Session, *, as_of: datetime) -> list[uuid.UUID]:
    stmt = select(FollowUp.id).where(FollowUp.status == FollowUpStatus.PENDING, FollowUp.due_at <= as_of)
    return list(db.execute(stmt).scalars().all())


def reclaim_stale_processing(db: Session, *, stale_before: datetime) -> int:
    """
    Safety net for a worker that died mid-send (crashed after claiming a
    row — status=PROCESSING — but before it could send or revert). Beat's
    scan resets anything stuck in PROCESSING past a threshold back to
    PENDING so it gets picked up again. Returns the number reset.
    """
    result = db.execute(
        update(FollowUp)
        .where(FollowUp.status == FollowUpStatus.PROCESSING, FollowUp.claimed_at < stale_before)
        .values(status=FollowUpStatus.PENDING, claimed_at=None)
    )
    db.commit()
    return result.rowcount


def try_claim(db: Session, follow_up_id: uuid.UUID, *, now: datetime) -> bool:
    """
    The atomic claim from the Phase 2/3 design: a single conditional
    UPDATE is row-locked and atomic in Postgres, so only one concurrent
    caller can ever see rowcount == 1 for a given follow-up. This is what
    makes reminder sending idempotent under concurrent/retried workers.
    """
    result = db.execute(
        update(FollowUp)
        .where(FollowUp.id == follow_up_id, FollowUp.status == FollowUpStatus.PENDING)
        .values(status=FollowUpStatus.PROCESSING, claimed_at=now)
    )
    db.commit()
    return result.rowcount == 1


def mark_sent(db: Session, follow_up_id: uuid.UUID) -> None:
    db.execute(update(FollowUp).where(FollowUp.id == follow_up_id).values(status=FollowUpStatus.SENT))
    db.commit()


def revert_to_pending(db: Session, follow_up_id: uuid.UUID) -> None:
    """Called when sending fails — makes the failure retryable, not lost."""
    db.execute(
        update(FollowUp)
        .where(FollowUp.id == follow_up_id)
        .values(status=FollowUpStatus.PENDING, claimed_at=None)
    )
    db.commit()
