"""
Billing tests: checkout-session authorization, and — the important part —
webhook signature verification and idempotency using REAL HMAC-signed
payloads constructed exactly the way Stripe signs them (per Stripe's
documented scheme: v1 = HMAC-SHA256("{timestamp}.{payload}", secret)).
No network call to Stripe is made or needed for any of this — signature
verification is entirely local cryptography.

Checkout-session creation itself (the one piece that requires an actual
network call to api.stripe.com) is NOT exercised here — this sandbox's
network egress doesn't reach Stripe, same restriction that applies to
Resend. See the milestone report for what that leaves for manual
verification with real Stripe test keys.
"""
import hashlib
import hmac
import json
import time

import pytest

from app.core.config import settings


def _register(client, email, name="Test User"):
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "full_name": name})
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_workspace(client, token, slug):
    resp = client.post("/api/v1/workspaces", json={"name": slug, "slug": slug}, headers=_auth_headers(token))
    assert resp.status_code == 201
    return resp.json()["id"]


WEBHOOK_SECRET = "whsec_test_secret_for_pytest_only"


def _sign_payload(payload_bytes: bytes, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    """Constructs a Stripe-Signature header exactly per Stripe's documented scheme."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.{payload_bytes.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"


def _stripe_event(event_type: str, event_id: str, obj: dict) -> bytes:
    return json.dumps({
        "id": event_id,
        "type": event_type,
        "data": {"object": obj},
    }).encode()


@pytest.fixture(autouse=True)
def _stripe_webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)


# ---------------------------------------------------------------------------
# GET billing / default subscription
# ---------------------------------------------------------------------------

def test_new_workspace_has_free_active_subscription(client):
    token = _register(client, "bill_a@test.com")
    ws_id = _create_workspace(client, token, "bill-ws-a")

    resp = client.get(f"/api/v1/workspaces/{ws_id}/billing", headers=_auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "FREE"
    assert body["status"] == "ACTIVE"


def test_checkout_session_requires_owner_role(client):
    owner_token = _register(client, "bill_b_owner@test.com")
    ws_id = _create_workspace(client, owner_token, "bill-ws-b")

    member_email = "bill_b_member@test.com"
    member_token = _register(client, member_email)
    client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": member_email, "role": "MEMBER"},
        headers=_auth_headers(owner_token),
    )

    resp = client.post(
        f"/api/v1/workspaces/{ws_id}/billing/checkout-session", headers=_auth_headers(member_token)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Webhook signature verification — the security-critical part
# ---------------------------------------------------------------------------

def test_webhook_rejects_invalid_signature(client):
    payload = _stripe_event("checkout.session.completed", "evt_test_1", {"id": "cs_test_1", "customer": "cus_1"})
    resp = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": "t=123,v1=deadbeef" * 4, "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_webhook_rejects_missing_signature_header(client):
    payload = _stripe_event("checkout.session.completed", "evt_test_2", {"id": "cs_test_2"})
    resp = client.post("/api/v1/billing/webhook", content=payload, headers={"content-type": "application/json"})
    assert resp.status_code == 400


def test_webhook_rejects_tampered_payload(client):
    """
    Signature is valid for the ORIGINAL payload, but the payload sent to
    the server is different — this is exactly what an attacker splicing
    a valid signature onto a modified body would attempt.
    """
    original_payload = _stripe_event("checkout.session.completed", "evt_test_3", {"id": "cs_test_3"})
    valid_signature_for_original = _sign_payload(original_payload)

    tampered_payload = _stripe_event("checkout.session.completed", "evt_test_3_evil", {"id": "cs_test_3_evil"})
    resp = client.post(
        "/api/v1/billing/webhook",
        content=tampered_payload,
        headers={"stripe-signature": valid_signature_for_original, "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_webhook_rejects_expired_timestamp_replay(client):
    """
    A signature valid in isolation but for a timestamp far in the past —
    Stripe's SDK enforces a tolerance window to block replay of an
    intercepted-but-old valid webhook call.
    """
    payload = _stripe_event("checkout.session.completed", "evt_test_4", {"id": "cs_test_4"})
    old_timestamp = int(time.time()) - 10_000  # well outside Stripe's default 300s tolerance
    signature = _sign_payload(payload, timestamp=old_timestamp)
    resp = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    assert resp.status_code == 400


def test_webhook_rejects_malformed_json_payload(client):
    garbage = b"this is not json at all {{{"
    signature = _sign_payload(garbage)
    resp = client.post(
        "/api/v1/billing/webhook",
        content=garbage,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Webhook processing — valid, correctly-signed events
# ---------------------------------------------------------------------------

def test_valid_checkout_completed_webhook_activates_pro(client):
    token = _register(client, "bill_c@test.com")
    ws_id = _create_workspace(client, token, "bill-ws-c")

    payload = _stripe_event(
        "checkout.session.completed",
        "evt_checkout_c",
        {"id": "cs_c", "customer": "cus_c", "subscription": "sub_c", "metadata": {"workspace_id": ws_id}},
    )
    signature = _sign_payload(payload)
    resp = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "checkout_completed_applied"

    billing = client.get(f"/api/v1/workspaces/{ws_id}/billing", headers=_auth_headers(token)).json()
    assert billing["plan"] == "PRO"
    assert billing["status"] == "ACTIVE"


def test_replayed_webhook_event_is_a_safe_no_op(client):
    """
    Duplicate-prevention: Stripe explicitly documents webhooks may be
    delivered more than once. The second delivery of the SAME event ID
    must be a harmless no-op, not reprocessed.
    """
    token = _register(client, "bill_d@test.com")
    ws_id = _create_workspace(client, token, "bill-ws-d")

    payload = _stripe_event(
        "checkout.session.completed",
        "evt_checkout_d_duplicate",
        {"id": "cs_d", "customer": "cus_d", "subscription": "sub_d", "metadata": {"workspace_id": ws_id}},
    )
    signature = _sign_payload(payload)
    headers = {"stripe-signature": signature, "content-type": "application/json"}

    first = client.post("/api/v1/billing/webhook", content=payload, headers=headers)
    second = client.post("/api/v1/billing/webhook", content=payload, headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "checkout_completed_applied"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_event_skipped"


def test_subscription_deleted_webhook_reverts_to_free(client):
    token = _register(client, "bill_e@test.com")
    ws_id = _create_workspace(client, token, "bill-ws-e")

    # First, activate Pro via checkout.session.completed.
    checkout_payload = _stripe_event(
        "checkout.session.completed",
        "evt_checkout_e",
        {"id": "cs_e", "customer": "cus_e", "subscription": "sub_e", "metadata": {"workspace_id": ws_id}},
    )
    client.post(
        "/api/v1/billing/webhook",
        content=checkout_payload,
        headers={"stripe-signature": _sign_payload(checkout_payload), "content-type": "application/json"},
    )

    # Then cancel it.
    deleted_payload = _stripe_event(
        "customer.subscription.deleted",
        "evt_deleted_e",
        {"id": "sub_e", "customer": "cus_e", "status": "canceled"},
    )
    resp = client.post(
        "/api/v1/billing/webhook",
        content=deleted_payload,
        headers={"stripe-signature": _sign_payload(deleted_payload), "content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "subscription_cancelled_applied"

    billing = client.get(f"/api/v1/workspaces/{ws_id}/billing", headers=_auth_headers(token)).json()
    assert billing["plan"] == "FREE"
    assert billing["status"] == "CANCELLED"


def test_subscription_updated_past_due(client):
    token = _register(client, "bill_f@test.com")
    ws_id = _create_workspace(client, token, "bill-ws-f")

    checkout_payload = _stripe_event(
        "checkout.session.completed",
        "evt_checkout_f",
        {"id": "cs_f", "customer": "cus_f", "subscription": "sub_f", "metadata": {"workspace_id": ws_id}},
    )
    client.post(
        "/api/v1/billing/webhook",
        content=checkout_payload,
        headers={"stripe-signature": _sign_payload(checkout_payload), "content-type": "application/json"},
    )

    updated_payload = _stripe_event(
        "customer.subscription.updated",
        "evt_updated_f",
        {"id": "sub_f", "customer": "cus_f", "status": "past_due"},
    )
    resp = client.post(
        "/api/v1/billing/webhook",
        content=updated_payload,
        headers={"stripe-signature": _sign_payload(updated_payload), "content-type": "application/json"},
    )
    assert resp.status_code == 200

    billing = client.get(f"/api/v1/workspaces/{ws_id}/billing", headers=_auth_headers(token)).json()
    assert billing["status"] == "PAST_DUE"


def test_unhandled_event_type_is_ignored_gracefully(client):
    payload = _stripe_event("payment_intent.succeeded", "evt_unhandled", {"id": "pi_1"})
    resp = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": _sign_payload(payload), "content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert "ignored_unhandled_type" in resp.json()["status"]
