"""
Celery tasks for the follow-up reminder system.

Business logic lives in plain functions (_send_reminder_for_follow_up,
_scan_due_follow_ups) that take a db session as a parameter — these are
directly unit-testable with a real Postgres session, with no broker or
running worker required. The @celery_app.task-decorated functions are
thin wrappers: open a session, call the logic, manage retry/backoff.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.integrations.email_client import EmailSendError, send_follow_up_reminder_email
from app.models import FollowUp, Lead, User
from app.repositories import follow_up_repository
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# If a worker dies mid-send (after claiming a row, before finishing),
# it's left stuck at PROCESSING. Beat's scan reclaims anything stuck
# longer than this back to PENDING.
STALE_PROCESSING_THRESHOLD_MINUTES = 10

# Manual exponential backoff for reminder-send retries: 30s, 60s, 120s,
# 240s, 480s, capped at 600s.
BASE_RETRY_DELAY_SECONDS = 30
MAX_RETRY_DELAY_SECONDS = 600


def _send_reminder_for_follow_up(db, follow_up_id) -> str:
    now = datetime.now(timezone.utc)
    claimed = follow_up_repository.try_claim(db, follow_up_id, now=now)
    if not claimed:
        # Another worker already claimed it, or its status changed
        # (cancelled/updated) since being scanned by Beat. Not an error —
        # this is exactly the scenario the atomic claim exists to handle.
        return "skipped_not_claimable"

    follow_up = db.get(FollowUp, follow_up_id)
    lead = db.get(Lead, follow_up.lead_id)
    assignee = db.get(User, follow_up.assigned_to) if follow_up.assigned_to else None

    if assignee is None:
        # No sensible recipient. Mark SENT (not left PENDING) so an
        # unassigned follow-up doesn't loop through Beat forever — this
        # is a data-shape gap, not a delivery failure to retry.
        follow_up_repository.mark_sent(db, follow_up_id)
        return "skipped_unassigned"

    send_follow_up_reminder_email(
        to_email=assignee.email,
        to_name=assignee.full_name,
        lead_name=lead.name,
        lead_company=lead.company,
        follow_up_title=follow_up.title,
        due_at_iso=follow_up.due_at.isoformat(),
    )
    follow_up_repository.mark_sent(db, follow_up_id)
    return "sent"


@celery_app.task(bind=True, max_retries=5)
def send_followup_reminder(self, follow_up_id: str):
    db = SessionLocal()
    try:
        return _send_reminder_for_follow_up(db, follow_up_id)
    except EmailSendError as exc:
        # Revert to PENDING *before* retrying (or giving up) — a failed
        # send must never leave the row stuck at PROCESSING, and this
        # runs whether or not retries remain, so exhausting max_retries
        # still leaves the follow-up in a retryable (PENDING) state for
        # the next Beat scan rather than silently dropping it.
        follow_up_repository.revert_to_pending(db, follow_up_id)
        logger.warning("Follow-up reminder send failed for %s: %s", follow_up_id, exc)
        backoff = min(BASE_RETRY_DELAY_SECONDS * (2**self.request.retries), MAX_RETRY_DELAY_SECONDS)
        raise self.retry(exc=exc, countdown=backoff)
    except Exception:
        follow_up_repository.revert_to_pending(db, follow_up_id)
        raise
    finally:
        db.close()


def _scan_due_follow_ups(db) -> list:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=STALE_PROCESSING_THRESHOLD_MINUTES)
    reclaimed = follow_up_repository.reclaim_stale_processing(db, stale_before=stale_before)
    if reclaimed:
        logger.info("Reclaimed %d stale PROCESSING follow-ups", reclaimed)
    return follow_up_repository.find_due_pending_ids(db, as_of=now)


@celery_app.task
def scan_due_followups():
    db = SessionLocal()
    try:
        due_ids = _scan_due_follow_ups(db)
    finally:
        db.close()

    for follow_up_id in due_ids:
        send_followup_reminder.delay(str(follow_up_id))
    return len(due_ids)
