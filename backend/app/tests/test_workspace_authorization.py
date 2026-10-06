"""
Workspace membership + role-based authorization tests.

Covers: workspace creation auto-assigns OWNER, non-members are blocked
(404, not 403 — see core/dependencies.py), and the OWNER/ADMIN/MEMBER
permission matrix from the Phase 1 spec is enforced server-side.
"""
import pytest


def _register(client, email, name="Test User"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": name},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_creating_workspace_makes_creator_owner(client):
    token = _register(client, "owner_a@test.com")
    resp = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-1"}, headers=_auth_headers(token))
    assert resp.status_code == 201
    workspace_id = resp.json()["id"]

    members = client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=_auth_headers(token))
    assert members.status_code == 200
    roles = {m["role"] for m in members.json()}
    assert roles == {"OWNER"}


def test_non_member_gets_404_not_403(client):
    owner_token = _register(client, "owner_b@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-2"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    outsider_token = _register(client, "outsider_b@test.com")
    resp = client.get(f"/api/v1/workspaces/{workspace_id}", headers=_auth_headers(outsider_token))
    # Must be 404, not 403 — a 403 would confirm the workspace exists to
    # someone with no relationship to it at all.
    assert resp.status_code == 404


def test_unauthenticated_request_is_401_not_404(client):
    owner_token = _register(client, "owner_c@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-3"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    resp = client.get(f"/api/v1/workspaces/{workspace_id}")
    assert resp.status_code == 401


def test_member_cannot_add_members(client):
    owner_token = _register(client, "owner_d@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-4"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    member_email = "member_d@test.com"
    _register(client, member_email)
    add_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    assert add_resp.status_code == 201
    member_token = _login(client, member_email)

    attempt = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "someoneelse_d@test.com", "role": "MEMBER"},
        headers=_auth_headers(member_token),
    )
    assert attempt.status_code == 403


def _login(client, email, password="password123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_admin_can_add_members_but_not_change_roles(client):
    owner_token = _register(client, "owner_e@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-5"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    admin_email = "admin_e@test.com"
    _register(client, admin_email)
    add_admin = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": admin_email, "role": "ADMIN"},
        headers=_auth_headers(owner_token),
    )
    assert add_admin.status_code == 201
    admin_member_id = add_admin.json()["id"]
    admin_token = _login(client, admin_email)

    # ADMIN can add a new member.
    _register(client, "newmember_e@test.com")
    add_result = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "newmember_e@test.com", "role": "MEMBER"},
        headers=_auth_headers(admin_token),
    )
    assert add_result.status_code == 201
    new_member_id = add_result.json()["id"]

    # ADMIN cannot change roles — OWNER-only per the permission matrix.
    role_change = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{new_member_id}",
        json={"role": "ADMIN"},
        headers=_auth_headers(admin_token),
    )
    assert role_change.status_code == 403


def test_owner_can_change_member_role(client):
    owner_token = _register(client, "owner_f@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-6"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    _register(client, "member_f@test.com")
    add_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "member_f@test.com", "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    member_id = add_resp.json()["id"]

    promote = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{member_id}",
        json={"role": "ADMIN"},
        headers=_auth_headers(owner_token),
    )
    assert promote.status_code == 200
    assert promote.json()["role"] == "ADMIN"


def test_cannot_change_owner_role_or_grant_ownership(client):
    owner_token = _register(client, "owner_g@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-7"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    members = client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=_auth_headers(owner_token))
    owner_member_id = members.json()[0]["id"]

    resp = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_member_id}",
        json={"role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    assert resp.status_code == 400

    _register(client, "wouldbeowner_g@test.com")
    add_resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "wouldbeowner_g@test.com", "role": "OWNER"},
        headers=_auth_headers(owner_token),
    )
    assert add_resp.status_code == 400


def test_cannot_remove_owner(client):
    owner_token = _register(client, "owner_h@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme", "slug": "acme-ws-8"}, headers=_auth_headers(owner_token))
    workspace_id = ws.json()["id"]

    members = client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=_auth_headers(owner_token))
    owner_member_id = members.json()[0]["id"]

    resp = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_member_id}", headers=_auth_headers(owner_token)
    )
    assert resp.status_code == 400


def test_cross_workspace_isolation_for_members_endpoint(client):
    """
    A member of workspace A must not be able to see or act on workspace
    B's members, even though both workspaces exist and both are real.
    """
    owner_a_token = _register(client, "owner_i@test.com")
    ws_a = client.post("/api/v1/workspaces", json={"name": "A", "slug": "ws-i-a"}, headers=_auth_headers(owner_a_token))
    ws_a_id = ws_a.json()["id"]

    owner_b_token = _register(client, "owner_j@test.com")
    ws_b = client.post("/api/v1/workspaces", json={"name": "B", "slug": "ws-i-b"}, headers=_auth_headers(owner_b_token))
    ws_b_id = ws_b.json()["id"]

    # Owner of A tries to list members of B.
    resp = client.get(f"/api/v1/workspaces/{ws_b_id}/members", headers=_auth_headers(owner_a_token))
    assert resp.status_code == 404
    assert ws_a_id != ws_b_id


def test_list_my_workspaces_returns_only_memberships(client):
    owner_a_token = _register(client, "listws_a@test.com")
    ws_a = client.post("/api/v1/workspaces", json={"name": "A", "slug": "listws-a"}, headers=_auth_headers(owner_a_token))
    ws_a_id = ws_a.json()["id"]

    owner_b_token = _register(client, "listws_b@test.com")
    client.post("/api/v1/workspaces", json={"name": "B", "slug": "listws-b"}, headers=_auth_headers(owner_b_token))

    resp = client.get("/api/v1/workspaces", headers=_auth_headers(owner_a_token))
    assert resp.status_code == 200
    ids = [w["id"] for w in resp.json()]
    assert ids == [ws_a_id]


def test_list_my_workspaces_includes_workspaces_joined_as_member(client):
    owner_token = _register(client, "listws_c_owner@test.com")
    ws = client.post("/api/v1/workspaces", json={"name": "C", "slug": "listws-c"}, headers=_auth_headers(owner_token))
    ws_id = ws.json()["id"]

    member_email = "listws_c_member@test.com"
    _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    member_token = _login(client, member_email)

    resp = client.get("/api/v1/workspaces", headers=_auth_headers(member_token))
    assert resp.status_code == 200
    assert [w["id"] for w in resp.json()] == [ws_id]


def test_list_my_workspaces_empty_for_new_user(client):
    token = _register(client, "listws_d@test.com")
    resp = client.get("/api/v1/workspaces", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_my_workspaces_requires_auth(client):
    resp = client.get("/api/v1/workspaces")
    assert resp.status_code == 401
