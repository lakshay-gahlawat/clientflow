"""
Model/DB-level tests for cross-workspace data-integrity invariants.

These specifically target the gaps identified in Phase 3 review:
  1. A FollowUp cannot reference a Lead belonging to a different workspace.
  2. Lead/FollowUp.assigned_to must belong to the SAME workspace as the
     record itself — assigning a user from another workspace is rejected.
  3. General regression coverage for the other FK/cascade behavior so a
     future change can't silently reopen these gaps.

Every "invalid" case below asserts an IntegrityError is raised — i.e. the
database itself refuses the bad data, not just application code.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User, Workspace, WorkspaceMember, Lead, FollowUp, Subscription
from app.models.enums import WorkspaceRole, FollowUpStatus


def make_user(db, email):
    u = User(email=email, hashed_password="x", full_name="Test User")
    db.add(u)
    db.flush()
    return u


def make_workspace(db, owner, slug):
    ws = Workspace(name=slug, slug=slug, owner_id=owner.id)
    db.add(ws)
    db.flush()
    return ws


def make_member(db, workspace, user, role=WorkspaceRole.MEMBER):
    m = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
    db.add(m)
    db.flush()
    return m


def make_lead(db, workspace, **kwargs):
    lead = Lead(
        workspace_id=workspace.id,
        name=kwargs.get("name", "Lead"),
        company=kwargs.get("company", "Co"),
        email=kwargs.get("email", "lead@example.com"),
        assigned_to=kwargs.get("assigned_to"),
    )
    db.add(lead)
    db.flush()
    return lead


# ---------------------------------------------------------------------------
# 1. FollowUp cannot reference a Lead from a different workspace
# ---------------------------------------------------------------------------

def test_followup_cannot_reference_lead_in_different_workspace(db):
    owner = make_user(db, "owner1@test.com")
    ws_a = make_workspace(db, owner, "workspace-a-1")
    ws_b = make_workspace(db, owner, "workspace-b-1")
    lead_in_a = make_lead(db, ws_a)

    # Attempt: a FollowUp claiming workspace_id = ws_b, but pointing at a
    # lead that actually belongs to ws_a. This is exactly the bug class
    # flagged in review — nothing but a mismatched workspace_id would have
    # stopped this before the composite FK was added.
    bad_followup = FollowUp(
        lead_id=lead_in_a.id,
        workspace_id=ws_b.id,
        title="Cross-tenant follow-up",
        due_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(bad_followup)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_followup_with_matching_workspace_succeeds(db):
    owner = make_user(db, "owner2@test.com")
    ws = make_workspace(db, owner, "workspace-match-1")
    lead = make_lead(db, ws)

    good_followup = FollowUp(
        lead_id=lead.id,
        workspace_id=ws.id,  # matches the lead's actual workspace
        title="Legit follow-up",
        due_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(good_followup)
    db.flush()  # should not raise
    assert good_followup.status == FollowUpStatus.PENDING


# ---------------------------------------------------------------------------
# 2. assigned_to must be a member of the SAME workspace
# ---------------------------------------------------------------------------

def test_lead_cannot_be_assigned_to_user_outside_workspace(db):
    owner = make_user(db, "owner3@test.com")
    ws_a = make_workspace(db, owner, "workspace-a-2")
    ws_b = make_workspace(db, owner, "workspace-b-2")

    outsider = make_user(db, "outsider@test.com")
    make_member(db, ws_b, outsider)  # outsider only belongs to ws_b

    # Attempt to assign a ws_a lead to a user who is only a member of ws_b.
    bad_lead = Lead(
        workspace_id=ws_a.id,
        name="Lead",
        company="Co",
        email="lead@example.com",
        assigned_to=outsider.id,
    )
    db.add(bad_lead)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_lead_can_be_assigned_to_actual_workspace_member(db):
    owner = make_user(db, "owner4@test.com")
    ws = make_workspace(db, owner, "workspace-c-1")
    member = make_user(db, "member4@test.com")
    make_member(db, ws, member)

    good_lead = make_lead(db, ws, assigned_to=member.id)
    assert good_lead.assigned_to == member.id


def test_followup_cannot_be_assigned_to_user_outside_workspace(db):
    owner = make_user(db, "owner5@test.com")
    ws_a = make_workspace(db, owner, "workspace-a-3")
    ws_b = make_workspace(db, owner, "workspace-b-3")
    lead = make_lead(db, ws_a)

    outsider = make_user(db, "outsider5@test.com")
    make_member(db, ws_b, outsider)

    bad_followup = FollowUp(
        lead_id=lead.id,
        workspace_id=ws_a.id,
        assigned_to=outsider.id,  # not a member of ws_a
        title="Bad assignment",
        due_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(bad_followup)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_removing_membership_blocked_while_still_assigned(db):
    """
    A WorkspaceMember row can't be deleted while a Lead/FollowUp in that
    workspace still points at them via the composite FK (NO ACTION, not
    CASCADE/SET NULL — see model comments for why). Confirms the assignee
    must be explicitly reassigned first, rather than assignments silently
    going stale.
    """
    owner = make_user(db, "owner6@test.com")
    ws = make_workspace(db, owner, "workspace-d-1")
    member = make_user(db, "member6@test.com")
    membership = make_member(db, ws, member)
    make_lead(db, ws, assigned_to=member.id)

    db.delete(membership)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ---------------------------------------------------------------------------
# 3. Regression coverage for existing FK/cascade behavior
# ---------------------------------------------------------------------------

def test_duplicate_workspace_membership_rejected(db):
    owner = make_user(db, "owner7@test.com")
    ws = make_workspace(db, owner, "workspace-e-1")
    make_member(db, ws, owner, role=WorkspaceRole.OWNER)

    dup = WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role=WorkspaceRole.ADMIN)
    db.add(dup)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_second_subscription_for_workspace_rejected(db):
    owner = make_user(db, "owner8@test.com")
    ws = make_workspace(db, owner, "workspace-f-1")
    db.add(Subscription(workspace_id=ws.id))
    db.flush()

    db.add(Subscription(workspace_id=ws.id))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_deleting_lead_cascades_to_its_followups(db):
    owner = make_user(db, "owner9@test.com")
    ws = make_workspace(db, owner, "workspace-g-1")
    lead = make_lead(db, ws)
    fu = FollowUp(
        lead_id=lead.id, workspace_id=ws.id,
        title="x", due_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.add(fu)
    db.flush()
    fu_id = fu.id

    db.delete(lead)
    db.flush()
    assert db.get(FollowUp, fu_id) is None


def test_deleting_workspace_owning_user_is_restricted(db):
    owner = make_user(db, "owner10@test.com")
    make_workspace(db, owner, "workspace-h-1")

    db.delete(owner)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_atomic_claim_only_one_worker_wins(db):
    """
    Regression check for the Phase 2 atomic-claim design: a conditional
    UPDATE ... WHERE status = 'PENDING' can only succeed once.
    """
    from sqlalchemy import update

    owner = make_user(db, "owner11@test.com")
    ws = make_workspace(db, owner, "workspace-i-1")
    lead = make_lead(db, ws)
    fu = FollowUp(
        lead_id=lead.id, workspace_id=ws.id,
        title="Claim test", due_at=datetime.now(timezone.utc),
    )
    db.add(fu)
    db.flush()

    stmt = (
        update(FollowUp)
        .where(FollowUp.id == fu.id, FollowUp.status == FollowUpStatus.PENDING)
        .values(status=FollowUpStatus.PROCESSING)
    )
    first = db.execute(stmt)
    second = db.execute(stmt)
    db.flush()

    assert first.rowcount == 1
    assert second.rowcount == 0
