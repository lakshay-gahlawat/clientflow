"""
Lead management tests: CRUD, search/filter/pagination, role-based
delete restriction, and — the most important case — cross-workspace
lead access isolation (a lead ID from workspace B must 404 when
requested through workspace A, not leak existence or data).
"""
import pytest


def _register(client, email, name="Test User"):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "full_name": name},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


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


def _create_lead(client, token, workspace_id, **overrides):
    payload = {
        "name": "Jane Doe",
        "company": "Acme Buyer Co",
        "email": "jane@buyer.com",
    }
    payload.update(overrides)
    resp = client.post(
        f"/api/v1/workspaces/{workspace_id}/leads", json=payload, headers=_auth_headers(token)
    )
    return resp


# ---------------------------------------------------------------------------
# CRUD basics
# ---------------------------------------------------------------------------

def test_create_lead_defaults_to_new_status(client):
    token = _register(client, "leadowner_a@test.com")
    ws_id = _create_workspace(client, token, "leads-ws-a")

    resp = _create_lead(client, token, ws_id)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "NEW"
    assert body["workspace_id"] == ws_id


def test_get_lead_returns_created_lead(client):
    token = _register(client, "leadowner_b@test.com")
    ws_id = _create_workspace(client, token, "leads-ws-b")
    lead_id = _create_lead(client, token, ws_id).json()["id"]

    resp = client.get(f"/api/v1/workspaces/{ws_id}/leads/{lead_id}", headers=_auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == lead_id


def test_update_lead_fields(client):
    token = _register(client, "leadowner_c@test.com")
    ws_id = _create_workspace(client, token, "leads-ws-c")
    lead_id = _create_lead(client, token, ws_id).json()["id"]

    resp = client.patch(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}",
        json={"company": "Updated Co", "notes": "Follow up next week"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["company"] == "Updated Co"
    assert body["notes"] == "Follow up next week"
    assert body["name"] == "Jane Doe"  # untouched field preserved


def test_update_lead_status(client):
    token = _register(client, "leadowner_d@test.com")
    ws_id = _create_workspace(client, token, "leads-ws-d")
    lead_id = _create_lead(client, token, ws_id).json()["id"]

    resp = client.patch(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}/status",
        json={"status": "QUALIFIED"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "QUALIFIED"


def test_delete_lead_as_owner_succeeds(client):
    token = _register(client, "leadowner_e@test.com")
    ws_id = _create_workspace(client, token, "leads-ws-e")
    lead_id = _create_lead(client, token, ws_id).json()["id"]

    resp = client.delete(f"/api/v1/workspaces/{ws_id}/leads/{lead_id}", headers=_auth_headers(token))
    assert resp.status_code == 204

    followup_check = client.get(f"/api/v1/workspaces/{ws_id}/leads/{lead_id}", headers=_auth_headers(token))
    assert followup_check.status_code == 404


# ---------------------------------------------------------------------------
# Authorization: role-gated delete, cross-workspace isolation
# ---------------------------------------------------------------------------

def test_member_can_create_and_update_leads(client):
    owner_token = _register(client, "leadowner_f@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-f")

    member_email = "leadmember_f@test.com"
    _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    member_token = _login(client, member_email)

    create_resp = _create_lead(client, member_token, ws_id)
    assert create_resp.status_code == 201
    lead_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/api/v1/workspaces/{ws_id}/leads/{lead_id}",
        json={"notes": "member update"},
        headers=_auth_headers(member_token),
    )
    assert update_resp.status_code == 200


def test_member_cannot_delete_lead(client):
    owner_token = _register(client, "leadowner_g@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-g")
    lead_id = _create_lead(client, owner_token, ws_id).json()["id"]

    member_email = "leadmember_g@test.com"
    _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    member_token = _login(client, member_email)

    resp = client.delete(f"/api/v1/workspaces/{ws_id}/leads/{lead_id}", headers=_auth_headers(member_token))
    assert resp.status_code == 403


def test_admin_can_delete_lead(client):
    owner_token = _register(client, "leadowner_h@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-h")
    lead_id = _create_lead(client, owner_token, ws_id).json()["id"]

    admin_email = "leadadmin_h@test.com"
    _register(client, admin_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": admin_email, "role": "ADMIN"},
        headers=_auth_headers(owner_token),
    )
    admin_token = _login(client, admin_email)

    resp = client.delete(f"/api/v1/workspaces/{ws_id}/leads/{lead_id}", headers=_auth_headers(admin_token))
    assert resp.status_code == 204


def test_cross_workspace_lead_access_returns_404(client):
    """
    The core isolation guarantee: a lead ID that genuinely exists (in
    workspace B) must 404 — not 403, not the actual data — when
    requested by a member of a completely different workspace A.
    """
    owner_a_token = _register(client, "leadowner_i@test.com")
    ws_a_id = _create_workspace(client, owner_a_token, "leads-ws-i-a")

    owner_b_token = _register(client, "leadowner_j@test.com")
    ws_b_id = _create_workspace(client, owner_b_token, "leads-ws-i-b")
    lead_in_b = _create_lead(client, owner_b_token, ws_b_id).json()["id"]

    # Owner of A tries to fetch B's lead through A's URL.
    resp = client.get(f"/api/v1/workspaces/{ws_a_id}/leads/{lead_in_b}", headers=_auth_headers(owner_a_token))
    assert resp.status_code == 404

    # Also blocked for update, status change, and delete.
    assert client.patch(
        f"/api/v1/workspaces/{ws_a_id}/leads/{lead_in_b}", json={"notes": "x"}, headers=_auth_headers(owner_a_token)
    ).status_code == 404
    assert client.patch(
        f"/api/v1/workspaces/{ws_a_id}/leads/{lead_in_b}/status",
        json={"status": "WON"},
        headers=_auth_headers(owner_a_token),
    ).status_code == 404
    assert client.delete(
        f"/api/v1/workspaces/{ws_a_id}/leads/{lead_in_b}", headers=_auth_headers(owner_a_token)
    ).status_code == 404

    # And the lead is genuinely untouched in its real workspace.
    still_there = client.get(
        f"/api/v1/workspaces/{ws_b_id}/leads/{lead_in_b}", headers=_auth_headers(owner_b_token)
    )
    assert still_there.status_code == 200
    assert still_there.json()["status"] == "NEW"


def test_cannot_assign_lead_to_non_member(client):
    owner_token = _register(client, "leadowner_k@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-k")

    outsider_token = _register(client, "outsider_k@test.com")
    outsider_me = client.get("/api/v1/auth/me", headers=_auth_headers(outsider_token)).json()

    resp = _create_lead(client, owner_token, ws_id, assigned_to=outsider_me["id"])
    assert resp.status_code == 400


def test_can_assign_lead_to_workspace_member(client):
    owner_token = _register(client, "leadowner_l@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-l")

    member_email = "leadmember_l@test.com"
    _register(client, member_email)
    add_resp = client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )
    member_user_id = add_resp.json()["user_id"]

    resp = _create_lead(client, owner_token, ws_id, assigned_to=member_user_id)
    assert resp.status_code == 201
    assert resp.json()["assigned_to"] == member_user_id


def test_unauthenticated_and_non_member_blocked(client):
    owner_token = _register(client, "leadowner_m@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-m")

    no_auth = client.get(f"/api/v1/workspaces/{ws_id}/leads")
    assert no_auth.status_code == 401

    outsider_token = _register(client, "outsider_m@test.com")
    non_member = client.get(f"/api/v1/workspaces/{ws_id}/leads", headers=_auth_headers(outsider_token))
    assert non_member.status_code == 404


# ---------------------------------------------------------------------------
# Search, filter, sort, pagination
# ---------------------------------------------------------------------------

def test_list_leads_filter_by_status(client):
    owner_token = _register(client, "leadowner_n@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-n")

    _create_lead(client, owner_token, ws_id, name="Lead One", email="one@x.com")
    won_lead = _create_lead(client, owner_token, ws_id, name="Lead Two", email="two@x.com").json()
    client.patch(
        f"/api/v1/workspaces/{ws_id}/leads/{won_lead['id']}/status",
        json={"status": "WON"},
        headers=_auth_headers(owner_token),
    )

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/leads", params={"status": "WON"}, headers=_auth_headers(owner_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Lead Two"


def test_list_leads_search_matches_name_company_email(client):
    owner_token = _register(client, "leadowner_o@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-o")

    _create_lead(client, owner_token, ws_id, name="Zephyr Corp Contact", company="Zephyr Corp", email="a@zephyr.com")
    _create_lead(client, owner_token, ws_id, name="Unrelated", company="Other Co", email="b@other.com")

    resp = client.get(
        f"/api/v1/workspaces/{ws_id}/leads", params={"search": "zephyr"}, headers=_auth_headers(owner_token)
    )
    body = resp.json()
    assert body["total"] == 1
    assert "Zephyr" in body["items"][0]["company"]


def test_list_leads_pagination(client):
    owner_token = _register(client, "leadowner_p@test.com")
    ws_id = _create_workspace(client, owner_token, "leads-ws-p")

    for i in range(5):
        _create_lead(client, owner_token, ws_id, name=f"Lead {i}", email=f"lead{i}@x.com")

    page1 = client.get(
        f"/api/v1/workspaces/{ws_id}/leads",
        params={"page": 1, "page_size": 2, "sort_by": "name", "sort_order": "asc"},
        headers=_auth_headers(owner_token),
    ).json()
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert page1["items"][0]["name"] == "Lead 0"

    page2 = client.get(
        f"/api/v1/workspaces/{ws_id}/leads",
        params={"page": 2, "page_size": 2, "sort_by": "name", "sort_order": "asc"},
        headers=_auth_headers(owner_token),
    ).json()
    assert page2["items"][0]["name"] == "Lead 2"


def test_list_leads_isolated_by_workspace(client):
    owner_a_token = _register(client, "leadowner_q@test.com")
    ws_a_id = _create_workspace(client, owner_a_token, "leads-ws-q-a")
    _create_lead(client, owner_a_token, ws_a_id, name="A Lead", email="a@a.com")

    owner_b_token = _register(client, "leadowner_r@test.com")
    ws_b_id = _create_workspace(client, owner_b_token, "leads-ws-q-b")
    _create_lead(client, owner_b_token, ws_b_id, name="B Lead", email="b@b.com")

    resp = client.get(f"/api/v1/workspaces/{ws_a_id}/leads", headers=_auth_headers(owner_a_token))
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "A Lead"
