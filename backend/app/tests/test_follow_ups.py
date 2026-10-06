"""
Follow-up API tests: CRUD, the MEMBER-can-only-touch-their-own permission
rule (stricter than Lead permissions — see follow_up_service docstring),
and tenant isolation.
"""
from datetime import datetime, timedelta, timezone

import pytest


def _register(client, email, name="Test User"):
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": name})
    assert resp.status_code == 201
    return resp.json()["access_token"], resp.json()["user"]["id"]


def _login(client, email, password="password123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_workspace(client, token, slug):
    resp = client.post("/api/v1/workspaces", json={"name": slug, "slug": slug}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_lead(client, token, workspace_id):
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads",
        json={"name": "Lead", "company": "Co", "email": "lead@x.com"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _due_at(minutes=60):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def test_create_follow_up_defaults_assignee_to_creator(client):
    token, user_id = _register(client, "fu_a@test.com")
    ws_id = _create_workspace(client, token, "fu-ws-a")
    lead_id = _create_lead(client, token, ws_id)

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Call back", "due_at": _due_at()},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["assigned_to"] == user_id
    assert body["status"] == "PENDING"


def test_member_cannot_create_follow_up_assigned_to_someone_else(client):
    owner_token, owner_id = _register(client, "fu_b_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-b")
    lead_id = _create_lead(client, owner_token, ws_id)

    member_email = "fu_b_member@test.com"
    member_token, member_id = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Call back", "due_at": _due_at(), "assigned_to": owner_id},
        headers=_auth_headers(member_token),
    )
    assert resp.status_code == 403


def test_owner_can_assign_follow_up_to_a_member(client):
    owner_token, _ = _register(client, "fu_c_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-c")
    lead_id = _create_lead(client, owner_token, ws_id)

    member_email = "fu_c_member@test.com"
    _, member_id = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Call back", "due_at": _due_at(), "assigned_to": member_id},
        headers=_auth_headers(owner_token),
    )
    assert resp.status_code == 201
    assert resp.json()["assigned_to"] == member_id


def test_member_cannot_modify_followup_assigned_to_someone_else(client):
    owner_token, owner_id = _register(client, "fu_d_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-d")
    lead_id = _create_lead(client, owner_token, ws_id)

    member_email = "fu_d_member@test.com"
    member_token, _ = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )

    # Owner creates a follow-up assigned to themselves (not the member).
    fu = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Owner's task", "due_at": _due_at()},
        headers=_auth_headers(owner_token),
    ).json()

    # Member tries to cancel it — should be blocked, it's not theirs.
    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/follow-ups/{fu['id']}/cancel", headers=_auth_headers(member_token)
    )
    assert resp.status_code == 403


def test_member_can_cancel_their_own_follow_up(client):
    owner_token, _ = _register(client, "fu_e_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-e")
    lead_id = _create_lead(client, owner_token, ws_id)

    member_email = "fu_e_member@test.com"
    member_token, member_id = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )

    fu = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "My task", "due_at": _due_at(), "assigned_to": member_id},
        headers=_auth_headers(owner_token),
    ).json()

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/follow-ups/{fu['id']}/cancel", headers=_auth_headers(member_token)
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_owner_can_manage_any_followup(client):
    owner_token, _ = _register(client, "fu_f_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-f")
    lead_id = _create_lead(client, owner_token, ws_id)

    member_email = "fu_f_member@test.com"
    member_token, member_id = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    fu = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Member's task", "due_at": _due_at(), "assigned_to": member_id},
        headers=_auth_headers(member_token),
    ).json()

    resp = client.post(f"/api/v1/workspaces/{ws_id}/follow-ups/{fu['id']}/cancel", headers=_auth_headers(owner_token))
    assert resp.status_code == 200


def test_list_mine_filters_to_current_user(client):
    owner_token, owner_id = _register(client, "fu_g_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-g")
    lead_id = _create_lead(client, owner_token, ws_id)

    member_email = "fu_g_member@test.com"
    member_token, member_id = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Owner task", "due_at": _due_at()},
        headers=_auth_headers(owner_token),
    )
    client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Member task", "due_at": _due_at(), "assigned_to": member_id},
        headers=_auth_headers(owner_token),
    )

    resp = client.get(f"/api/v1/workspaces/{ws_id}/follow-ups?mine=true", headers=_auth_headers(member_token))
    assert resp.status_code == 200
    titles = [f["title"] for f in resp.json()]
    assert titles == ["Member task"]


def test_cannot_cancel_already_sent_follow_up(client, db):
    from app.models import FollowUp
    from app.models.enums import FollowUpStatus

    owner_token, _ = _register(client, "fu_h_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "fu-ws-h")
    lead_id = _create_lead(client, owner_token, ws_id)
    fu = client.post(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/follow-ups",
        json={"title": "Task", "due_at": _due_at()},
        headers=_auth_headers(owner_token),
    ).json()

    # Directly flip it to SENT via the SAME session the API requests
    # share in this test (client's dependency override points at `db`)
    # — simulating what the worker does, without crossing connections.
    db.query(FollowUp).filter(FollowUp.id == fu["id"]).update({"status": FollowUpStatus.SENT})
    db.commit()

    resp = client.post(f"/api/v1/workspaces/{ws_id}/follow-ups/{fu['id']}/cancel", headers=_auth_headers(owner_token))
    assert resp.status_code == 400


def test_cross_workspace_follow_up_access_returns_404(client):
    owner_a_token, _ = _register(client, "fu_i_a@test.com")
    ws_a_id = _create_workspace(client, owner_a_token, "fu-ws-i-a")
    lead_a_id = _create_lead(client, owner_a_token, ws_a_id)
    fu = client.post(
        f"/api/v1/workspaces/{ws_a_id}/leads/{lead_a_id}/follow-ups",
        json={"title": "Task", "due_at": _due_at()},
        headers=_auth_headers(owner_a_token),
    ).json()

    owner_b_token, _ = _register(client, "fu_i_b@test.com")
    ws_b_id = _create_workspace(client, owner_b_token, "fu-ws-i-b")

    resp = client.patch(
        f"/api/v1/workspaces/{ws_b_id}/follow-ups/{fu['id']}", json={"title": "hijacked"}, headers=_auth_headers(owner_b_token)
    )
    assert resp.status_code == 404


def test_create_follow_up_for_lead_in_different_workspace_404s(client):
    owner_a_token, _ = _register(client, "fu_j_a@test.com")
    ws_a_id = _create_workspace(client, owner_a_token, "fu-ws-j-a")
    lead_a_id = _create_lead(client, owner_a_token, ws_a_id)

    owner_b_token, _ = _register(client, "fu_j_b@test.com")
    ws_b_id = _create_workspace(client, owner_b_token, "fu-ws-j-b")

    # Owner of B tries to create a follow-up under A's lead via B's URL.
    resp = client.post(
        f"/api/v1/workspaces/{ws_b_id}/leads/{lead_a_id}/follow-ups",
        json={"title": "Task", "due_at": _due_at()},
        headers=_auth_headers(owner_b_token),
    )
    assert resp.status_code == 404
