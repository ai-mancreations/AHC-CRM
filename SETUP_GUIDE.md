# American Hair Club CRM — Setup Guide

A full CRM and business management platform for American Hair Club's 4 branches
(Hyderabad, Pune, Vizag, Bangalore): Marketing → Lead → Appointment → Service →
Invoice → Revenue → Reporting.

**Stack:** React + Vite + TypeScript (frontend) · FastAPI + Beanie/Motor (backend)
· MongoDB · Celery + Redis · WeasyPrint (PDFs) · Cloudinary (file storage) ·
deploys on Render.

---

## 1. First 10 minutes — run it locally with Docker

The fastest way to see the whole app working, with 12 months of realistic
demo data already loaded.

```bash
git clone <this-repo>
cd american-hair-club
docker compose up --build
```

This starts MongoDB, Redis, the FastAPI backend (port 8000), a Celery worker,
and the Vite dev server (port 5173).

Once containers are up, load the demo data (only needs to be run once):

```bash
docker compose exec backend python seed.py
```

Then open **http://localhost:5173** and log in:

| Role | Email | Password |
|---|---|---|
| Super Admin | `admin@americanhairclub.in` | `Admin@123` |
| Manager | `manager@americanhairclub.in` | `Manager@123` |

*(Check `seed.py`'s printed output — the exact demo email domain and
lead-count summary is echoed there each time you run it.)*

Every screen — dashboards, leads kanban, customers, inventory, invoices,
expenses — is populated immediately.

### Re-running the seed
`seed.py` **wipes and reloads every collection** each time you run it, so it's
always safe to re-run to reset the demo environment:
```bash
docker compose exec backend python seed.py
```

---

## 2. Running without Docker

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit MONGO_URI to point at your Mongo instance
uvicorn app.main:app --reload
```

**Celery worker** (separate terminal, needed for ad-sync, low-stock alerts,
follow-up/maintenance reminders, and message sending):
```bash
celery -A app.jobs.celery_app worker --beat --loglevel=info
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 3. Environment variables

### Backend (`backend/.env`)

| Variable | What it's for | How to get it |
|---|---|---|
| `MONGO_URI` | MongoDB connection string | Local dev: `mongodb://localhost:27017` (or the docker-compose `mongo` service). Production: create a free/paid cluster at [MongoDB Atlas](https://www.mongodb.com/atlas), Database Access → add a user, Network Access → allow your Render service IPs (or 0.0.0.0/0), then copy the "Connect your application" string. |
| `JWT_SECRET` | Signs login tokens | Any long random string. Render's blueprint auto-generates one. |
| `FERNET_KEY` | Encrypts integration credentials (Google/Meta Ads keys, WhatsApp tokens) at rest | Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Stores generated invoice PDFs and staff photos | Free account at [cloudinary.com](https://cloudinary.com) → Dashboard shows all three values immediately after signup. |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Background job queue (ad sync, alerts, reminders, message sending) | Local: `redis://localhost:6379/0`. Render: the `render.yaml` blueprint provisions a managed Redis instance and wires this automatically. |
| `CORS_ORIGINS` | Which frontend origin(s) may call the API | Your frontend's deployed URL, e.g. `https://ahc-frontend.onrender.com` |
| `FY_START_MONTH` | Indian financial year start (April) | Leave as `4` unless your accounting FY differs |

WhatsApp/SMS/Email provider credentials aren't separate env vars — they're
entered per-provider from **Settings → Integrations** in the app itself (Super
Admin only), where they're encrypted with `FERNET_KEY` before being stored.
Until you add real credentials there, messaging and ad-sync tasks run in
**stub mode**: they log what *would* be sent/synced instead of calling a real
provider, so the whole workflow (templates, triggers, campaign dashboards)
is fully testable without live accounts. See
`backend/app/jobs/tasks_messaging.py` and `backend/app/jobs/tasks_ads.py` for
where to plug in real provider SDKs later.

### Frontend
No required env vars — API calls go through the `/api` path, which Vite
proxies to `localhost:8000` in dev (`vite.config.ts`) and which your hosting
platform rewrites to the backend service in production (`render.yaml`).

---

## 4. Deploying to Render

1. Push this repo to GitHub.
2. In Render, choose **New → Blueprint**, point it at your repo — it will
   read `render.yaml` at the repo root and provision:
   - `ahc-backend` — the FastAPI web service (Docker)
   - `ahc-celery-worker` — background worker for scheduled/async jobs
   - `ahc-frontend` — the static React build, with `/api/*` rewritten to
     the backend
   - `ahc-redis` — managed Redis for Celery
3. Fill in the env vars marked `sync: false` in the Render dashboard
   (`MONGO_URI`, `FERNET_KEY`, Cloudinary keys) — see the table above.
4. Once the backend is live, run the seed script once from a Render shell
   (or locally against the Atlas URI) to load demo data:
   ```bash
   python seed.py
   ```

---

## 5. Public lead form embed

The unauthenticated lead-intake endpoint is `POST /api/public/lead-form`
(rate-limited to 5 submissions per IP per 10 minutes). Embed a simple form on
the marketing website that POSTs `{ branch_id, name, phone, email,
visit_reason, utm_source, utm_medium, utm_campaign, message }` to
`https://<your-backend-domain>/api/public/lead-form`. Branch IDs are visible
via `GET /api/branches` (no auth required for reading branch names — if you'd
rather not expose that publicly, hardcode the 4 branch IDs into the embed
script after your first deploy).

---

## 6. GST & financial year setup

Each branch's GSTIN and state code are set when the branch is created
(`Settings` are Super-Admin-only in the UI; the 4 demo branches are already
seeded with real Telangana/Maharashtra/Andhra Pradesh/Karnataka state codes).
CGST+SGST vs IGST is computed automatically per invoice by comparing the
branch's state code to the customer's `gst_state_code`. Invoice numbers are
generated atomically per branch per financial year (format
`AHC/{BRANCH}/{FY}/{seq:04d}`) via a Mongo counter, so concurrent invoice
creation can never collide. FY start month (default April = `4`) is set in
Settings → Company/GST Config.

---

## 7. What's stubbed vs. production-ready

Everything in the data model, GST/invoicing math, atomic numbering, RBAC,
audit logging, and the core operational workflows (leads → appointments →
services → invoices → payments, inventory deduction, dashboards/profit
charts) is fully implemented and runs against real data.

Three integration points are intentionally stubbed behind clean interfaces,
since they require real third-party credentials you don't have yet:
- **Google Ads / Meta Ads sync** (`app/jobs/tasks_ads.py`) — swap in real API
  calls once you have ad account credentials in Settings → Integrations.
- **WhatsApp/SMS/Email sending** (`app/jobs/tasks_messaging.py`) — swap in a
  real provider SDK (WhatsApp Cloud API, Twilio, SES/SMTP) the same way.
- **AI Assistant** (`app/services/ai_query.py`) — currently uses a lightweight
  keyword classifier (no external LLM call) so the feature works out of the
  box; the docstring in that file explains exactly how to route it through a
  real Claude API call while keeping the same "never run arbitrary queries"
  safety guarantee.

The frontend covers the core flows end-to-end (dashboards, leads kanban,
customers/360°, invoices, inventory, expenses, marketing, AI assistant,
settings, audit log) with the specified premium dark/gold visual style. A few
of the more elaborate UI specifics from the original brief — full drag-drop
reordering in Settings, CSV/Excel export buttons wired to the existing
`/api/reports/*.csv` endpoints, and the Cmd+K global search — have working
backend endpoints already but light or no frontend UI yet; wiring those up is
the natural next increment.
