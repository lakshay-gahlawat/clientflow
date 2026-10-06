"""
Root-level pytest conftest — runs before app/tests/conftest.py and
before any test module is collected. Two jobs, both aimed at making
`pytest` a single, reproducible, documented command that doesn't require
hand-exporting environment variables:

1. Load .env.test into the process environment BEFORE anything under
   app/ gets imported. app/core/config.py's `Settings()` singleton is
   instantiated at import time, so this must happen first — if any test
   module imported app.db.session before this ran, it would silently
   pick up backend/.env (the dev config) instead, or fail outright if no
   .env exists at all.

   override=False deliberately: if a CI environment has already exported
   real env vars (e.g. a managed test-database URL, secrets), those take
   priority over .env.test's defaults rather than being clobbered by them.
   For a plain local `pytest` run with nothing pre-exported, .env.test's
   values are what get used.

2. Apply Alembic migrations against the test database automatically, so
   a fresh clone only needs the one-time `createdb clientflow_test` step
   (documented in the README) before `pytest` just works — no separate
   manual migration command.
"""
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env.test", override=False)

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def _apply_test_migrations():
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")
    yield
