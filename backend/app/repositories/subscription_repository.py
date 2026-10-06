import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Subscription
from app.models.enums import SubscriptionPlan, SubscriptionStatus


def create_default(db: Session, *, workspace_id: uuid.UUID) -> Subscription:
    sub = Subscription(workspace_id=workspace_id, plan=SubscriptionPlan.FREE, status=SubscriptionStatus.ACTIVE)
    db.add(sub)
    db.flush()
    return sub


def get_by_workspace(db: Session, workspace_id: uuid.UUID) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.workspace_id == workspace_id).first()


def get_by_stripe_customer_id(db: Session, stripe_customer_id: str) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.stripe_customer_id == stripe_customer_id).first()


def get_by_stripe_subscription_id(db: Session, stripe_subscription_id: str) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_subscription_id).first()
