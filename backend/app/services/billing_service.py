"""
Billing business logic.

The single most important property of this file: local subscription
state changes ONLY happen in handle_webhook_event, driven by a
signature-verified Stripe event. create_checkout_session never touches
subscription state itself — it just starts a Stripe-hosted flow. The
frontend's "success" redirect after checkout is purely a UX signal (see
BillingPage) and carries zero authority over the database.
"""
import logging
import uuid

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.integrations.stripe_client import StripeConfigError, create_checkout_session
from app.models import Subscription, Workspace
from app.models.enums import SubscriptionPlan, SubscriptionStatus
from app.repositories import stripe_event_repository, subscription_repository

logger = logging.getLogger(__name__)

_STRIPE_STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELLED,
    "unpaid": SubscriptionStatus.PAST_DUE,
    "incomplete": SubscriptionStatus.INCOMPLETE,
    "incomplete_expired": SubscriptionStatus.INCOMPLETE,
}


def get_or_create_subscription(db: Session, workspace: Workspace) -> Subscription:
    # Backward compatibility: workspaces created before this phase don't
    # have a Subscription row yet (see workspace_service.create_workspace
    # for where new ones now get one atomically).
    sub = subscription_repository.get_by_workspace(db, workspace.id)
    if sub is None:
        sub = subscription_repository.create_default(db, workspace_id=workspace.id)
        db.commit()
        db.refresh(sub)
    return sub


def start_checkout(db: Session, *, workspace: Workspace, frontend_base_url: str) -> str:
    subscription = get_or_create_subscription(db, workspace)
    if subscription.plan == SubscriptionPlan.PRO and subscription.status == SubscriptionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This workspace is already on Pro")

    try:
        session = create_checkout_session(
            workspace_id=str(workspace.id),
            workspace_name=workspace.name,
            existing_customer_id=subscription.stripe_customer_id,
            success_url=f"{frontend_base_url}/billing?checkout=success",
            cancel_url=f"{frontend_base_url}/billing?checkout=cancelled",
        )
    except StripeConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except stripe.error.StripeError as exc:
        logger.error("Stripe checkout session creation failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Couldn't start checkout with Stripe")

    if not session.url:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Stripe did not return a checkout URL")
    return session.url


def _find_subscription_for_event(db: Session, event_object: dict) -> Subscription | None:
    """
    Resolves a Stripe event object back to a local Subscription row.
    Tries, in order: metadata.workspace_id (set at checkout-session
    creation), the Stripe subscription ID, then the Stripe customer ID —
    covering checkout.session.completed (has workspace_id metadata and a
    customer) and customer.subscription.* events (have a subscription ID
    and customer, may or may not carry the metadata depending on how
    Stripe surfaces it).
    """
    workspace_id = (event_object.get("metadata") or {}).get("workspace_id")
    if workspace_id:
        sub = subscription_repository.get_by_workspace(db, uuid.UUID(workspace_id))
        if sub:
            return sub

    stripe_sub_id = event_object.get("subscription") or (
        event_object.get("id") if event_object.get("object") == "subscription" else None
    )
    if stripe_sub_id:
        sub = subscription_repository.get_by_stripe_subscription_id(db, stripe_sub_id)
        if sub:
            return sub

    customer_id = event_object.get("customer")
    if customer_id:
        return subscription_repository.get_by_stripe_customer_id(db, customer_id)

    return None


def handle_webhook_event(db: Session, event: stripe.Event) -> str:
    """
    Returns a short status string for logging/testing — never raises for
    "this event type isn't handled" (Stripe sends many event types we
    don't care about; ignoring them is correct, not an error).

    Idempotency: checked FIRST, before any side effect, using Stripe's
    own event ID (not derived from the payload) — a retried delivery of
    an event we've already applied is a fast, side-effect-free no-op.
    """
    stripe_event_id = event["id"]
    if stripe_event_repository.already_processed(db, stripe_event_id):
        return "duplicate_event_skipped"

    event_type = event["type"]
    obj = event["data"]["object"]
    result = _apply_event(db, event_type, obj)

    # Recorded after successful processing, in the same commit boundary
    # as the state change it corresponds to isn't strictly required here
    # since each branch already commits — recorded right after so a
    # crash between state-commit and this record would, at worst, cause
    # one harmless reprocessing on retry (the state changes are
    # themselves idempotent — see _apply_event), never data loss.
    stripe_event_repository.record(db, stripe_event_id=stripe_event_id, event_type=event_type)
    db.commit()
    return result


def _apply_event(db: Session, event_type: str, obj: dict) -> str:

    if event_type == "checkout.session.completed":
        workspace_id = (obj.get("metadata") or {}).get("workspace_id") or obj.get("client_reference_id")
        if not workspace_id:
            logger.warning("checkout.session.completed with no workspace_id metadata: %s", obj.get("id"))
            return "ignored_no_workspace_id"

        sub = subscription_repository.get_by_workspace(db, uuid.UUID(workspace_id))
        if sub is None:
            logger.warning("checkout.session.completed for unknown workspace %s", workspace_id)
            return "ignored_unknown_workspace"

        sub.stripe_customer_id = obj.get("customer")
        sub.stripe_subscription_id = obj.get("subscription")
        sub.plan = SubscriptionPlan.PRO
        sub.status = SubscriptionStatus.ACTIVE
        db.commit()
        return "checkout_completed_applied"

    if event_type in ("customer.subscription.updated", "customer.subscription.created"):
        sub = _find_subscription_for_event(db, obj)
        if sub is None:
            logger.warning("customer.subscription.updated for unmatched subscription %s", obj.get("id"))
            return "ignored_unmatched_subscription"

        sub.stripe_subscription_id = obj.get("id")
        stripe_status = obj.get("status")
        sub.status = _STRIPE_STATUS_MAP.get(stripe_status, SubscriptionStatus.INCOMPLETE)
        sub.plan = SubscriptionPlan.PRO if sub.status == SubscriptionStatus.ACTIVE else sub.plan
        period_end = obj.get("current_period_end")
        if period_end:
            from datetime import datetime, timezone

            sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
        db.commit()
        return "subscription_updated_applied"

    if event_type == "customer.subscription.deleted":
        sub = _find_subscription_for_event(db, obj)
        if sub is None:
            logger.warning("customer.subscription.deleted for unmatched subscription %s", obj.get("id"))
            return "ignored_unmatched_subscription"

        sub.status = SubscriptionStatus.CANCELLED
        sub.plan = SubscriptionPlan.FREE
        db.commit()
        return "subscription_cancelled_applied"

    return f"ignored_unhandled_type:{event_type}"
