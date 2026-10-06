"""
Stripe integration — checkout session creation and webhook signature
verification.

Uses the official `stripe` SDK rather than hand-rolled HTTP calls: unlike
the single simple POST to Resend, Stripe Checkout Sessions have enough
surface area (line items, customer creation/reuse, success/cancel URLs,
metadata) that the SDK is the right tool, not unnecessary complexity.
"""
import stripe

from app.core.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeConfigError(Exception):
    """Raised when Stripe isn't configured — missing secret key, price ID, etc."""


def create_checkout_session(
    *, workspace_id: str, workspace_name: str, existing_customer_id: str | None, success_url: str, cancel_url: str
) -> stripe.checkout.Session:
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID_PRO:
        raise StripeConfigError("Stripe is not configured (STRIPE_SECRET_KEY / STRIPE_PRICE_ID_PRO)")

    session_kwargs = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICE_ID_PRO, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        # Ties the session back to the workspace unambiguously — the
        # webhook handler uses this, not anything the frontend reports,
        # to know which workspace a completed checkout belongs to.
        "metadata": {"workspace_id": workspace_id},
        "subscription_data": {"metadata": {"workspace_id": workspace_id}},
    }
    if existing_customer_id:
        session_kwargs["customer"] = existing_customer_id
    else:
        session_kwargs["customer_email"] = None  # left for Stripe Checkout to collect
        session_kwargs["client_reference_id"] = workspace_id

    return stripe.checkout.Session.create(**session_kwargs)


def verify_webhook_signature(*, payload: bytes, signature_header: str) -> stripe.Event:
    """
    Raises stripe.error.SignatureVerificationError on an invalid or
    tampered payload — the caller (the webhook route) turns that into a
    400, never processing an unverified event.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise StripeConfigError("STRIPE_WEBHOOK_SECRET is not configured")
    return stripe.Webhook.construct_event(payload, signature_header, settings.STRIPE_WEBHOOK_SECRET)
