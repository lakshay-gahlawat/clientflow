"""
Shared enum types, implemented as native Postgres ENUMs.
Each is given an explicit `name=` so Alembic autogenerate treats it as a
first-class type (CREATE TYPE / ALTER TYPE) instead of guessing.
"""
import enum


class WorkspaceRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    PROPOSAL = "PROPOSAL"
    WON = "WON"
    LOST = "LOST"


class FollowUpStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"  # atomic claim in-flight — see Phase 2 design
    SENT = "SENT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SubscriptionPlan(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    INCOMPLETE = "INCOMPLETE"
