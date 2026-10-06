"""
Importing every model here ensures they're registered on Base.metadata
before Alembic's autogenerate (or any create_all) runs.
"""
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.models.subscription import Subscription
from app.models.refresh_token import RefreshToken
from app.models.stripe_event import StripeEvent

__all__ = ["User", "Workspace", "WorkspaceMember", "Lead", "FollowUp", "Subscription", "RefreshToken", "StripeEvent"]
