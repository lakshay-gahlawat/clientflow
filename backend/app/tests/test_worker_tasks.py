"""
Tests for the follow-up reminder worker: due-follow-up scanning, atomic
claiming (duplicate-prevention), successful delivery, and retry/backoff
on failure — with Resend's HTTP call mocked (no real API key available
in this environment; see integrations/email_client.py for the real
implementation, unit-tested here via monkeypatch rather than a live call).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.integrations.email_client import EmailSendError
from app.models import FollowUp, Lead, User, Workspace, WorkspaceMember
from app.models.enums import FollowUpStatus, WorkspaceRole
from app.repositories import follow_up_repository
from app.workers.tasks import _scan_due_follow_ups, _send_reminder_for_follow_up, send_followup_reminder


def _make_workspace_with_lead_and_assignee(db):
    user = User(email=f"worker-{id(db)}@test.com", hashed_password="x", full_name="Worker Test User")
    db.add(user); db.flush()
    ws = Workspace(name="W", slug=f"worker-ws-{id(db)}", owner_id=user.id)
    db.add(ws); db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER)); db.flush()
    lead = Lead(workspace_id=ws.id, name="Lead", company="Co", email="lead@x.com")
    db.add(lead); db.flush()
    return user, ws, lead


def _make_follow_up(db, ws, lead, *, assigned_to=None, due_in_minutes=-5, status_=FollowUpStatus.PENDING):
    fu = FollowUp(
        lead_id=lead.id, workspace_id=ws.id, assigned_to=assigned_to,
        title="Reminder", due_at=datetime.now(timezone.utc) + timedelta(minutes=due_in_minutes),
        status=status_,
    )
    db.add(fu); db.commit()
    return fu


# ---------------------------------------------------------------------------
# Scheduling: finding due follow-ups
# ---------------------------------------------------------------------------

def test_scan_finds_due_pending_follow_ups(db):
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    due = _make_follow_up(db, ws, lead, assigned_to=user.id, due_in_minutes=-5)
    not_due = _make_follow_up(db, ws, lead, assigned_to=user.id, due_in_minutes=60)

    due_ids = _scan_due_follow_ups(db)
    assert due.id in due_ids
    assert not_due.id not in due_ids


def test_scan_reclaims_stale_processing_follow_ups(db):
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    stuck = _make_follow_up(db, ws, lead, assigned_to=user.id, due_in_minutes=-30, status_=FollowUpStatus.PROCESSING)
    # Simulate a worker that claimed it 20 minutes ago and then died.
    db.query(FollowUp).filter(FollowUp.id == stuck.id).update(
        {"claimed_at": datetime.now(timezone.utc) - timedelta(minutes=20)}
    )
    db.commit()

    due_ids = _scan_due_follow_ups(db)
    db.refresh(stuck)
    assert stuck.status == FollowUpStatus.PENDING
    assert stuck.id in due_ids  # reclaimed AND immediately eligible again


def test_scan_does_not_reclaim_recently_claimed_processing(db):
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    fresh = _make_follow_up(db, ws, lead, assigned_to=user.id, due_in_minutes=-5, status_=FollowUpStatus.PROCESSING)
    db.query(FollowUp).filter(FollowUp.id == fresh.id).update({"claimed_at": datetime.now(timezone.utc)})
    db.commit()

    _scan_due_follow_ups(db)
    db.refresh(fresh)
    assert fresh.status == FollowUpStatus.PROCESSING  # left alone, still in-flight


# ---------------------------------------------------------------------------
# Duplicate prevention: atomic claim
# ---------------------------------------------------------------------------

def test_only_one_claim_succeeds_for_concurrent_attempts(db):
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    fu = _make_follow_up(db, ws, lead, assigned_to=user.id)

    first = follow_up_repository.try_claim(db, fu.id, now=datetime.now(timezone.utc))
    second = follow_up_repository.try_claim(db, fu.id, now=datetime.now(timezone.utc))
    assert first is True
    assert second is False


def test_sending_a_follow_up_twice_only_sends_once(db):
    """
    Simulates Beat somehow enqueueing the same follow-up ID twice (e.g. a
    slow scan overlapping the next one) — the second invocation of the
    actual send logic must no-op, not send a duplicate email.
    """
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    fu = _make_follow_up(db, ws, lead, assigned_to=user.id)

    with patch("app.workers.tasks.send_follow_up_reminder_email") as mock_send:
        first_result = _send_reminder_for_follow_up(db, fu.id)
        second_result = _send_reminder_for_follow_up(db, fu.id)

    assert first_result == "sent"
    assert second_result == "skipped_not_claimable"
    assert mock_send.call_count == 1  # the actual email call only fired once


# ---------------------------------------------------------------------------
# Delivery: success path
# ---------------------------------------------------------------------------

def test_successful_send_marks_follow_up_sent(db):
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    fu = _make_follow_up(db, ws, lead, assigned_to=user.id)

    with patch("app.workers.tasks.send_follow_up_reminder_email") as mock_send:
        result = _send_reminder_for_follow_up(db, fu.id)

    assert result == "sent"
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == user.email
    db.refresh(fu)
    assert fu.status == FollowUpStatus.SENT


def test_unassigned_follow_up_is_marked_sent_without_calling_email(db):
    user, ws, lead = _make_workspace_with_lead_and_assignee(db)
    fu = _make_follow_up(db, ws, lead, assigned_to=None)

    with patch("app.workers.tasks.send_follow_up_reminder_email") as mock_send:
        result = _send_reminder_for_follow_up(db, fu.id)

    assert result == "skipped_unassigned"
    mock_send.assert_not_called()
    db.refresh(fu)
    assert fu.status == FollowUpStatus.SENT


# ---------------------------------------------------------------------------
# Retry / backoff on failure — the exact path the live sandbox network
# restriction accidentally exercised for real against api.resend.com.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Retry / backoff on failure — the exact path the live sandbox network
# restriction accidentally exercised for real against api.resend.com.
#
# These two tests exercise send_followup_reminder directly (not
# _send_reminder_for_follow_up) specifically because the task opens its
# OWN SessionLocal() — a separate DB connection, exactly as it would
# running in a real worker process. That means setup data must be
# actually committed (not left inside the `db` fixture's uncommitted
# SAVEPOINT transaction, which is invisible to a different connection)
# — so these use a real, self-cleaning session instead of the `db` fixture.
# ---------------------------------------------------------------------------

@pytest.fixture()
def committed_follow_up():
    """
    Creates a real, COMMITTED user/workspace/lead/follow-up — needed so
    the task's independent SessionLocal() connection can actually see it.
    Cleans itself up afterward (via workspace-delete cascade, per the
    Phase 3 FK design) since nothing here is auto-rolled-back — wrapped
    in try/finally so a failing test doesn't leave orphaned rows behind
    for the next run.
    """
    import uuid as uuid_module
    from app.db.session import SessionLocal

    unique = uuid_module.uuid4().hex[:8]
    session = SessionLocal()
    user = User(email=f"worker-retry-test-{unique}@test.com", hashed_password="x", full_name="Worker Retry Test")
    session.add(user); session.commit()
    ws = Workspace(name="W", slug=f"worker-retry-test-ws-{unique}", owner_id=user.id)
    session.add(ws); session.commit()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER)); session.commit()
    lead = Lead(workspace_id=ws.id, name="Lead", company="Co", email="lead@x.com")
    session.add(lead); session.commit()
    fu = FollowUp(
        lead_id=lead.id, workspace_id=ws.id, assigned_to=user.id,
        title="Reminder", due_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        status=FollowUpStatus.PENDING,
    )
    session.add(fu); session.commit()
    follow_up_id, workspace_id, user_id = fu.id, ws.id, user.id

    try:
        yield follow_up_id, user.email
    finally:
        # Core-level delete (not session.delete()) — bypasses SQLAlchemy's
        # ORM-level cascade ordering entirely and lets Postgres's own
        # ON DELETE CASCADE constraints (verified in Phase 3) handle
        # workspace_members/leads/follow_ups in one statement, regardless
        # of what the test did to the follow-up's status in the meantime.
        from sqlalchemy import delete as sa_delete

        session.rollback()
        session.execute(sa_delete(Workspace).where(Workspace.id == workspace_id))
        session.execute(sa_delete(User).where(User.id == user_id))
        session.commit()
        session.close()


def test_send_failure_reverts_to_pending_not_left_stuck(committed_follow_up):
    from app.db.session import SessionLocal

    follow_up_id, _ = committed_follow_up
    with patch("app.workers.tasks.send_follow_up_reminder_email", side_effect=EmailSendError("boom")):
        # .apply() defaults to throw=False: it returns an EagerResult with
        # state/result set rather than raising into the caller. The
        # traceback logged to stderr during this call is Celery's own
        # internal failure logging (trace_task), not a propagated
        # exception — a real worker process behaves the same way.
        result = send_followup_reminder.apply(args=[str(follow_up_id)])

    assert result.state == "FAILURE"
    assert isinstance(result.result, EmailSendError)

    check_session = SessionLocal()
    fu = check_session.get(FollowUp, follow_up_id)
    assert fu.status == FollowUpStatus.PENDING
    assert fu.claimed_at is None
    check_session.close()


def test_retry_is_attempted_max_retries_plus_one_times(committed_follow_up):
    follow_up_id, _ = committed_follow_up
    with patch(
        "app.workers.tasks.send_follow_up_reminder_email", side_effect=EmailSendError("boom")
    ) as mock_send:
        result = send_followup_reminder.apply(args=[str(follow_up_id)])

    assert result.state == "FAILURE"
    # max_retries=5 on the task → 1 initial attempt + 5 retries = 6 calls.
    # Each one re-claims the row (PENDING was reverted after the previous
    # failure), sends, fails, and retries — confirming the manual
    # exponential-backoff retry loop actually runs the expected number
    # of times rather than silently giving up early or looping forever.
    assert mock_send.call_count == 6
