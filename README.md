# ClientFlow

A B2B lead & client management SaaS — portfolio/case-study project
demonstrating a complete, tested, production-shaped web application:
FastAPI + PostgreSQL backend, React frontend, async background
processing, and Stripe billing.

## Features

- **Authentication** — registration, login, short-lived JWT access
  tokens, httpOnly refresh-token cookies with rotation and CSRF
  protection, session restoration on page reload.
- **Workspaces** — multi-tenant by design (`workspace_id` on every
  tenant-owned row, enforced by composite foreign keys — not just
  application-level filtering), workspace switching, role-based
  permissions (Owner / Admin / Member).
- **Leads** — full CRUD, search, filter, sort, pagination, assignment,
  pipeline-stage tracking.
- **Pipeline** — leads grouped by stage with stage-change controls.
- **Follow-ups** — due-date reminders, background-processed and emailed
  asynchronously via Celery + Redis + Resend, with atomic claiming (no
  duplicate sends), retry with backoff, and stale-task recovery.
- **Billing** — Stripe Checkout for a Free → Pro upgrade, subscription
  state driven exclusively by verified, idempotent Stripe webhooks —
  never by a frontend redirect.
- **Team management** — invite members, change roles, remove members,
  all permission-gated both server-side (the real enforcement) and
  client-side (so the UI doesn't show actions that would just fail).

## Architecture

```
Frontend (React + TS + Vite + Tailwind)
        │  REST/JSON, JWT + httpOnly cookie
        ▼
Backend (FastAPI) ── routes → services → repositories → PostgreSQL
        │
        ├── enqueues ──► Redis ──► Celery worker ──► Resend (email)
        │                            ▲
        │                Celery Beat │ (periodic due-follow-up scan)
        │
        └── Stripe Checkout + verified webhooks ──► subscriptions table
```

Full diagrams (system architecture, ERD, auth flow, Celery/Stripe
sequence) are in [`docs/architecture-diagram.md`](docs/architecture-diagram.md).

## Tech stack

**Backend:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis, Celery
(worker + Beat), Stripe SDK, python-jose, bcrypt.
**Frontend:** React, TypeScript, Vite, Tailwind CSS, React Router,
TanStack Query, Axios.
**Infra:** Docker Compose (dev and production configurations), nginx
(production frontend serving).

## Local development setup

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# edit backend/.env: set a real JWT_SECRET_KEY
#   python -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose up --build
```

That's the whole setup — the backend container runs `alembic upgrade
head` automatically before starting (see `backend/Dockerfile`), so a
fresh clone doesn't need a separate manual migration step.

- API: http://localhost:8000 (interactive docs at `/docs`)
- Frontend: http://localhost:5173
- Health check: `GET /health`

## Database migrations

Applied automatically on every `docker compose up` (see above — safe to
run repeatedly, Alembic no-ops when already at head). For manual use —
rolling back, or running against a database outside Docker:

```bash
cd backend
alembic upgrade head        # apply all pending migrations
alembic downgrade -1         # roll back one migration
alembic revision --autogenerate -m "description"   # after a model change
```

Every migration in this project has been verified with a full
`upgrade → downgrade → upgrade` roundtrip against a real Postgres
instance before being committed.

## Running background workers

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info    # processes reminder sends
celery -A app.workers.celery_app beat --loglevel=info       # schedules the periodic due-follow-up scan
```

Both are already wired into `docker-compose.yml` (dev) and
`docker-compose.prod.yml` (production) as separate services — you don't
need to run them manually unless debugging.

## Running tests

**Backend** — one-time setup (a dedicated test database, kept separate
from dev data):

```bash
createdb -h localhost -U clientflow clientflow_test
cd backend
pip install -r requirements.txt
pytest
```

That's the whole workflow — no manually-exported environment variables.
`backend/.env.test` (committed — dummy values, not a real secret) is
loaded automatically by `backend/conftest.py` before any app code
imports, which also applies migrations to the test database as a
session-scoped fixture. Tests run against real Postgres and (where
relevant) real Redis, not mocks or SQLite — several tested invariants
(composite foreign keys, native enum types, atomic row-claiming) are
Postgres-specific and don't exist under a lighter-weight substitute.

Current status: **90/90 backend tests passing**, covering auth, CSRF,
refresh-token rotation and reuse-detection, tenant isolation, RBAC
across every role/action combination, lead CRUD and pagination,
follow-up permission rules, Celery task scheduling/claiming/retry/
backoff (against a real worker process and real Redis), and Stripe
webhook signature verification with genuinely malicious/malformed
payloads (bad signature, tampered payload, expired timestamp replay,
malformed JSON).

**Frontend:**

```bash
cd frontend
npm install
npm test                # Vitest — AuthContext session lifecycle and the
                         # API client's refresh-on-401 interceptor logic
npx tsc -b --noEmit      # type check
npx vite build           # production build
```

## Stripe setup

1. Create a [Stripe account](https://dashboard.stripe.com) (test mode
   is fine for development).
2. Create a Product with a recurring Price for the Pro plan; copy its
   Price ID into `STRIPE_PRICE_ID_PRO`.
3. Copy your test-mode secret key into `STRIPE_SECRET_KEY`.
4. For webhooks: in test mode, use the
   [Stripe CLI](https://stripe.com/docs/stripe-cli) (`stripe listen
   --forward-to localhost:8000/api/v1/billing/webhook`) to get a local
   webhook secret; in production, register the real endpoint URL
   (`https://your-api-domain/api/v1/billing/webhook`) in the Stripe
   Dashboard and use the signing secret it gives you.
5. **Manual verification still required**: this sandbox environment's
   network egress cannot reach `api.stripe.com`, so checkout-session
   creation and the full checkout → webhook round trip have not been
   exercised against real Stripe infrastructure. Webhook signature
   verification, idempotency, and event-handling logic ARE fully tested
   locally (see `backend/app/tests/test_billing.py`) using real
   HMAC-signed payloads constructed exactly as Stripe signs them — but
   confirm the live flow manually with Stripe test-mode keys before
   relying on it in production.

## Email (Resend) setup

1. Create a [Resend account](https://resend.com), verify a sending
   domain, and generate an API key.
2. Set `RESEND_API_KEY` and `EMAIL_FROM` (must be on the verified domain).
3. **Manual verification required** for the same reason as Stripe: this
   environment's network egress cannot reach `api.resend.com`. The
   send/failure/retry logic is fully tested locally with the HTTP call
   mocked (`backend/app/tests/test_worker_tasks.py`); during
   implementation, an unmocked attempt against the real endpoint was
   blocked by this sandbox's network policy, which incidentally
   exercised and confirmed the retry-and-revert-to-PENDING failure path
   for real. Confirm actual email delivery manually once deployed.

## Deployment

### Render (live)

This repo includes a [Render Blueprint](https://render.com/docs/blueprint-spec) in `render.yaml`.

1. Push to GitHub (public or private; connect the GitHub app on Render).
2. Open [New Blueprint Instance](https://dashboard.render.com/blueprint/new) and select this repository.
3. Apply the blueprint. The public app is the **clientflow-web** service (nginx). API traffic stays on the same origin at `/api`.
4. After the first deploy, set `CORS_ORIGINS` on **clientflow-api** to `["https://<your-clientflow-web>.onrender.com"]` if the generated hostname differs.
5. Optional: add Stripe and Resend keys on **clientflow-api** (and the webhook URL `https://<web-host>/api/v1/billing/webhook`) when you want billing and reminder email.

Postgres and Redis on Render are paid add-ons; web/worker services use the Starter plan in the blueprint.

### Docker Compose (self-hosted)

```bash
cp .env.example .env    # fill in real production values — see comments in the file
docker compose -f docker-compose.prod.yml up -d --build
```

Differences from the dev compose file: no `--reload`, no source
bind-mounts (images are immutable, rebuilt per deploy), the frontend is
served by nginx instead of the Vite dev server, `restart:
unless-stopped` on every long-running service, and all configuration
comes from environment variables — nothing is baked into the compose
file itself.

Before going live, also:
- Put a real reverse proxy / TLS terminator in front of this (not
  covered here — nginx in this repo only serves the frontend's static
  files, it isn't configured as a public-facing TLS proxy).
- Enable Redis auth (`requirepass`) if Redis is reachable outside the
  Docker network — the bundled `redis:7-alpine` service has none
  configured, appropriate only for a private compose network.
- Set real, non-wildcard `CORS_ORIGINS`.
- Generate a fresh `JWT_SECRET_KEY` — never reuse the dev value.

## Key engineering decisions

- **Row-level multi-tenancy, not schema-per-tenant** — `workspace_id`
  on every tenant-owned table, enforced by composite foreign keys (a
  follow-up's `workspace_id` must match its lead's actual
  `workspace_id`; an assignee must actually be a member of that
  workspace) rather than relying solely on application-code filtering.
- **Access tokens in memory only** — never localStorage, never
  sessionStorage. Refresh tokens are httpOnly cookies, hashed at rest;
  reuse of an already-rotated refresh token revokes every session for
  that user (theft/replay signal).
- **404, not 403, for cross-tenant access** — a non-member requesting a
  resource in a workspace they don't belong to gets the same response
  whether that workspace exists or not, so membership can't be probed.
- **Webhook state is the only source of truth for billing** — a
  frontend "checkout succeeded" redirect is purely a UX signal; the
  database only changes from a signature-verified Stripe event.
- **Atomic claim, not a status check-then-set** — both follow-up
  reminder sending and Stripe webhook processing use a pattern that's
  safe under concurrent/duplicate delivery (a single conditional
  `UPDATE ... WHERE status = X`, or an idempotency-key table), not a
  read-then-write race.
