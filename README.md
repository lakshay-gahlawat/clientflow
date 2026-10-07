# ClientFlow

A B2B lead & client management SaaS — portfolio/case-study project
demonstrating a complete, tested, production-shaped web application:
FastAPI + PostgreSQL backend, React frontend, async background
processing, and Stripe billing.

## Live demo

| | Link |
|---|---|
| **Live app** | https://clientflow-plum.vercel.app |
| **API** | https://clientflow-backend-qdv4.onrender.com |
| **API docs (Swagger)** | https://clientflow-backend-qdv4.onrender.com/docs |
| **Health check** | https://clientflow-backend-qdv4.onrender.com/health |

> **Note:** the backend runs on free-tier hosting. If the app has been idle,
> the first request can take up to a minute while the server wakes up.
> Later requests are fast.


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

### Production topology

```
Browser ──► Vercel (static React app)
              │
              │  /api/*  (rewrite / proxy, see frontend/vercel.json)
              ▼
         Render (FastAPI) ──► Neon (PostgreSQL)
                          └─► Redis
```

The browser only ever talks to one origin (the Vercel domain). Vercel
forwards `/api/*` to the backend, so there is no cross-site CORS and the
httpOnly refresh cookie and CSRF cookie behave as first-party cookies.

## Tech stack

**Backend:** FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis, Celery
(worker + Beat), Stripe SDK, python-jose, bcrypt.
**Frontend:** React, TypeScript, Vite, Tailwind CSS, React Router,
TanStack Query, Axios.
**Infra:** Vercel (frontend), Render (API), Neon (PostgreSQL),
Docker Compose (dev and production configurations), nginx (production
frontend serving in the Compose setup).

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

## Environment variables

### Backend (Render / `backend/.env`)

| Variable | Example | Notes |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables `Secure` cookies and HSTS. Use `development` locally. |
| `DATABASE_URL` | `postgresql://user:pass@host/db?sslmode=require` | For Neon, use the pooled connection string and keep the database in the **same region** as the API. Remove `&channel_binding=require` if present. |
| `REDIS_URL` | `redis://...` | Used for rate limiting and Celery. |
| `JWT_SECRET_KEY` | _random 64+ chars_ | Generate a fresh one for production. |
| `CORS_ORIGINS` | `["https://clientflow-plum.vercel.app"]` | JSON array **or** comma-separated list. No trailing slash. |
| `STRIPE_SECRET_KEY` | `sk_test_...` | Optional — billing. |
| `STRIPE_PRICE_ID_PRO` | `price_...` | Optional — billing. |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | Optional — billing. |
| `RESEND_API_KEY` | `re_...` | Optional — reminder emails. |
| `EMAIL_FROM` | `ClientFlow <noreply@yourdomain.com>` | Must be on a verified Resend domain. |

### Frontend (Vercel / `frontend/.env`)

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `/api/v1` | Same-origin path; Vercel proxies it to the API. Vite reads this at **build time**, so redeploy after changing it. |

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
   (`https://clientflow-plum.vercel.app/api/v1/billing/webhook`) in the
   Stripe Dashboard and use the signing secret it gives you.
5. **Manual verification recommended**: webhook signature verification,
   idempotency, and event-handling logic are fully tested locally (see
   `backend/app/tests/test_billing.py`) using real HMAC-signed payloads
   constructed exactly as Stripe signs them. The full checkout → webhook
   round trip against live Stripe infrastructure should still be
   confirmed manually with Stripe test-mode keys before relying on it in
   production.

## Email (Resend) setup

1. Create a [Resend account](https://resend.com), verify a sending
   domain, and generate an API key.
2. Set `RESEND_API_KEY` and `EMAIL_FROM` (must be on the verified domain).
3. **Manual verification recommended**: the send/failure/retry logic is
   fully tested locally with the HTTP call mocked
   (`backend/app/tests/test_worker_tasks.py`). Confirm actual email
   delivery manually once deployed. Reminders also require the Celery
   worker and Beat processes to be running.

## Deployment

### Option A: Vercel (frontend) + Render (API) + Neon (database) — current live setup

**1. Database (Neon)**
- Create a Neon project in the **same region as your Render service**
  (for example Singapore for both). A region mismatch adds a long round
  trip to every query and makes the whole app feel slow.
- Copy the **pooled** connection string and remove
  `&channel_binding=require` if present. Keep `?sslmode=require`.

**2. Backend (Render)**
- Create a Web Service from this repo with the root directory set to
  `backend`, using the Dockerfile (it runs `alembic upgrade head` before
  starting).
- Set the backend environment variables from the table above, including
  `ENVIRONMENT=production`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`
  and `CORS_ORIGINS`.
- Verify: `https://<your-api>.onrender.com/health` returns
  `{"status":"ok", ...}`.

**3. Frontend (Vercel)**
- Import the repo and set **Root Directory** to `frontend`
  (Framework: Vite, Build: `npm run build`, Output: `dist`).
- Add the environment variable `VITE_API_BASE_URL=/api/v1`.
- Make sure `frontend/vercel.json` exists and points at your API:

```json
  {
    "rewrites": [
      { "source": "/api/:path*", "destination": "https://<your-api>.onrender.com/api/:path*" },
      { "source": "/((?!api/).*)", "destination": "/index.html" }
    ]
  }
```

  The first rule proxies API calls to Render; the second keeps React
  Router pages working on refresh.
- Verify: `https://<your-app>.vercel.app/api/v1/auth/me` should return
  `{"detail":"Not authenticated"}`.

**4. Finish**
- Set `CORS_ORIGINS` on Render to your exact Vercel URL (no trailing
  slash), then redeploy.

### Option B: Render Blueprint

This repo includes a [Render Blueprint](https://render.com/docs/blueprint-spec) in `render.yaml`.

1. Push to GitHub (public or private; connect the GitHub app on Render).
2. Open [New Blueprint Instance](https://dashboard.render.com/blueprint/new) and select this repository.
3. Apply the blueprint. The public app is the **clientflow-web** service (nginx). API traffic stays on the same origin at `/api`.
4. After the first deploy, set `CORS_ORIGINS` on **clientflow-api** to `["https://<your-clientflow-web>.onrender.com"]` if the generated hostname differs.
5. Optional: add Stripe and Resend keys on **clientflow-api** (and the webhook URL `https://<web-host>/api/v1/billing/webhook`) when you want billing and reminder email.

Postgres and Redis on Render are paid add-ons; web/worker services use the Starter plan in the blueprint.

### Option C: Docker Compose (self-hosted)

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

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| "Can't reach the server" | CORS or network failure. Check that `CORS_ORIGINS` on the API exactly matches the frontend origin (no trailing slash), and that the API is awake (`/health`). |
| API crashes on startup with a settings error | `CORS_ORIGINS` format. Use a JSON array or a comma-separated list, and make sure `DATABASE_URL`, `REDIS_URL` and `JWT_SECRET_KEY` are all set. |
| Vercel shows its own "This page doesn't exist" for `/api/...` | `vercel.json` isn't in the deployed build. Confirm it is in `frontend/`, that Vercel's Root Directory is `frontend`, and that the latest commit was deployed (check the deployment's Source tab). |
| Login works but you're logged out on reload | Cookies not first-party. Use the Vercel `/api` proxy (`VITE_API_BASE_URL=/api/v1`) and set `ENVIRONMENT=production`. |
| Every request takes 2–3 seconds | API and database in different regions. Put them in the same region and use the pooled Neon connection string. |
| First request after idle takes up to a minute | Free-tier cold start on Render. Use a paid plan or an uptime monitor pinging `/health`. |
| Changed `VITE_API_BASE_URL` but nothing happened | Vite bakes env vars in at build time. Trigger a fresh deployment. |

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
- **Same-origin API via a proxy** — the frontend calls `/api/v1/...` on
  its own domain and the host forwards it to the backend, which avoids
  cross-site cookie and CORS problems for the httpOnly refresh cookie
  and CSRF double-submit flow.