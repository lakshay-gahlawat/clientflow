"""
Declarative base for all ORM models.
Models are imported here in Phase 3 so Alembic's autogenerate can see them.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
