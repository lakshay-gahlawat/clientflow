"""
Pytest fixtures for model- and API-level tests. Runs against a real
Postgres database (not SQLite) — Phase 3's composite FKs and native enum
types are Postgres-specific and don't exist under SQLite's relaxed FK
enforcement.

.env.test loading and migration setup live in the root-level
backend/conftest.py (runs first, before this module is imported) — not
duplicated here.

Each test runs inside an outer transaction + a SAVEPOINT (nested
transaction). Tests intentionally trigger IntegrityErrors and call
db.rollback() mid-test to recover and keep asserting — a plain
connection.begin() would deassociate on that rollback and corrupt
isolation between tests. Restarting the SAVEPOINT on every
`after_transaction_end` event is what makes that safe.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.db.session import engine, get_db
from app.main import app
import os

os.environ["RATELIMIT_ENABLED"] = "False"

@pytest.fixture(autouse=True)
def bypass_rate_limits(monkeypatch):
    """Bypasses rate limiting for all unit tests."""
    monkeypatch.setenv("RATELIMIT_ENABLED", "False")

@pytest.fixture()
def db():
    connection = engine.connect()
    connection.begin()
    SessionForTest = sessionmaker(bind=connection)
    session = SessionForTest()

    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        connection.close()


@pytest.fixture()
def client(db):
    """
    TestClient wired to the SAME transactional session as the `db`
    fixture, via FastAPI's dependency_override mechanism — so API-level
    tests get the same rollback-per-test isolation as direct model tests.
    """

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
