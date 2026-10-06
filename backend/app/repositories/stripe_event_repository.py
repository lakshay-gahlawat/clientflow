from typing import Optional

from sqlalchemy.orm import Session

from app.models import StripeEvent


def already_processed(db: Session, stripe_event_id: str) -> bool:
    return (
        db.query(StripeEvent).filter(StripeEvent.stripe_event_id == stripe_event_id).first() is not None
    )


def record(db: Session, *, stripe_event_id: str, event_type: str) -> StripeEvent:
    record_ = StripeEvent(stripe_event_id=stripe_event_id, event_type=event_type)
    db.add(record_)
    db.flush()
    return record_
