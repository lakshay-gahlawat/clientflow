import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import require_workspace_member, require_workspace_role
from app.db.session import get_db
from app.integrations.stripe_client import StripeConfigError, verify_webhook_signature
from app.models import WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories import workspace_repository
from app.schemas.billing import CheckoutSessionResponse, SubscriptionRead
from app.services import billing_service

router = APIRouter()


@router.get("/workspaces/{workspace_id}/billing", response_model=SubscriptionRead, tags=["billing"])
def get_billing(
    workspace_id: str,
    membership: WorkspaceMember = Depends(require_workspace_member),
    db: Session = Depends(get_db),
):
    workspace = workspace_repository.get_by_id(db, workspace_id)
    subscription = billing_service.get_or_create_subscription(db, workspace)
    return SubscriptionRead.model_validate(subscription)


@router.post(
    "/workspaces/{workspace_id}/billing/checkout-session",
    response_model=CheckoutSessionResponse,
    tags=["billing"],
)
def create_checkout_session_endpoint(
    workspace_id: str,
    # Billing is OWNER-only, per the Phase 1 permission matrix ("OWNER:
    # Full workspace control, Billing").
    membership: WorkspaceMember = Depends(require_workspace_role(WorkspaceRole.OWNER)),
    db: Session = Depends(get_db),
):
    workspace = workspace_repository.get_by_id(db, workspace_id)
    checkout_url = billing_service.start_checkout(
        db, workspace=workspace, frontend_base_url=settings.CORS_ORIGINS[0]
    )
    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/billing/webhook", status_code=status.HTTP_200_OK, tags=["billing"])
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    signature_header = request.headers.get("stripe-signature", "")

    try:
        event = verify_webhook_signature(payload=payload, signature_header=signature_header)
    except StripeConfigError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except stripe.error.SignatureVerificationError:
        # Never process an unverified payload — this is the single most
        # important line in this file. A 400 here, not a 200, so Stripe
        # (or an attacker) gets no ambiguity about whether it was accepted.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
    except ValueError:
        # Malformed JSON — construct_event's json.loads raises a plain
        # ValueError (JSONDecodeError) for this, separately from Stripe's
        # own SignatureVerificationError. A garbage/truncated body must
        # 400 just as cleanly as a bad signature, not surface as an
        # unhandled 500. Caught here explicitly rather than assumed.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook payload")

    result = billing_service.handle_webhook_event(db, event)
    return {"status": result}
