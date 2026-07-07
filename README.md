# Karuna Admin — Project Administration Platform

A project administration platform. Configure a project by submitting its
**master plan** (typed or uploaded as a document); the AI (xAI **Grok**) parses
it into objectives and generates the client deliverables automatically. Separate
Kanban workspaces track dev code-review and commercial (new-business) work.

## Panels & workspaces

| Area | Purpose | AI |
|------|---------|----|
| **① Setup** | Submit the master plan — type it or **upload PDF/DOCX/TXT**; text is extracted and fed to Grok, which generates deliverables. | ✅ Grok |
| **Code Review** | Per-project Kanban for dev follow-up (Backlog → To do → In progress → In review → Done). Drag-and-drop, assignees, PR links. | ❌ AI-free |
| **Deliverables** | Client deliverables grouped by objective, each with a **Grok AI-analysis subpanel** scoring it 0–100 against the plan. | ✅ Grok |
| **Client Monitoring** | Non-technical visual progress: completion ring + per-objective bars. | derived |
| **Ticket Monitor** (`/tickets`) | Every dev ticket across **all** projects in one board, filterable. | ❌ |
| **Commercial** (`/commercial`) | Global pipeline boards (Lead → … → Won/Lost) for sourcing **new IT projects**, with company/value/pipeline totals. | ❌ AI-free |
| **Team** (`/users`) | Role-scoped user creation & directory. | — |

## Architecture

```
frontend (React + Vite + TS)  ──HTTP──▶  backend (Python / FastAPI)  ──▶  MySQL
        served by FastAPI                        │
                                                 └──▶ Grok (xAI) for AI generation/analysis
realtime (Node/TS ws)  ──▶  optional live Kanban sync
```

- **backend/** — Python **FastAPI** + SQLAlchemy + **MySQL**. Auth (JWT), roles,
  projects, file upload + text extraction, deliverables, Grok AI, dev Kanban,
  commercial boards, cross-project tickets, client monitoring.
- **frontend/** — **React + Vite + TypeScript** SPA. In production it's built and
  served by the FastAPI backend, so the whole app deploys as **one service**.
- **realtime/** — thin **Node/TypeScript** WebSocket gateway for live Kanban
  sync. Optional.

### Grok AI (xAI)
OpenAI-compatible xAI API (`https://api.x.ai/v1`, model `grok-4.3`). Set
`GROK_API_KEY` to enable it; **without a key it runs in deterministic mock mode**
so the platform is fully runnable — mock analyses are labelled `(mock)`.
**AI analysis is internal-only** — it is never returned to or shown to clients.

### Email notifications (Resend)
Set `RESEND_API_KEY` (+ `RESEND_FROM` on a verified domain, and `APP_BASE_URL`
for links) to email users on assignments and additions — deliverable assigned,
deliverable submitted (→ dev admins), dev ticket assigned, commercial
opportunity assigned, and new-user welcome. Without a key, notifications are
logged only, so nothing breaks. Emails send in the background and never block a
request.

### Deliverable documents & client submissions
Deliverables can be **assigned to any user, including a client**. The assignee
uploads documentation to the deliverable and hits **Submit**; dev admins are
notified. Files are stored in MySQL. Dev admins can upload/download on any
deliverable; the assignee can upload/download on theirs.

## Deploy on Railway (single service)

One service builds the root `Dockerfile` (frontend → bundled into the FastAPI
image) plus the MySQL plugin:

1. **MySQL** plugin — exposes `MYSQL_URL`.
2. **App service** — Root Directory = repo root (auto-detects the root
   `Dockerfile`). Variables:
   - `DATABASE_URL` → `${{MySQL.MYSQL_URL}}` (auto-normalized to the PyMySQL driver)
   - `JWT_SECRET` → long random string
   - `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_NAME` → bootstrap super admin
   - `GROK_API_KEY` → your xAI key (omit for mock mode); `GROK_MODEL=grok-4.3`
   - `CORS_ORIGINS` → not needed for single-service (same origin); `*` is fine

The app is served at `/`, the API under `/api`, docs at `/docs`.

## Local development

```bash
docker compose up --build      # full stack incl. MySQL
# then http://localhost:5173
```
Or run pieces individually — see `backend/.env.example` and `frontend/.env.example`.
A zero-setup DB works too: `DATABASE_URL=sqlite:///./dev.db`.

## Roles & permissions

| Role | Can do |
|------|--------|
| `admin` | Super admin — everything (bootstrap account) |
| `admin_dev` | Full access, dev-focused: projects, master plan + file upload, deliverables & AI, dev boards, ticket monitor; creates `dev` users |
| `admin_comercial` | Manages the commercial team & boards; creates `comercial` users |
| `dev` | Edit/assign tickets on the dev code-review boards |
| `comercial` | Edit/assign opportunities on the commercial boards |
| `client` | Read-only client monitoring |

Enforced server-side in `app/permissions.py` and mirrored in the UI. `admin` is
included in every permission group, so it always has access.

### Live-DB migration
`app/seed.py` runs an idempotent startup migration that widens the MySQL
`users.role` column from the old `ENUM` to `VARCHAR(32)` and renames the legacy
`developer` role to `dev`, so existing deployments upgrade with no manual SQL.

## Key API routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` · GET `/api/auth/me` | Auth |
| GET/POST | `/api/auth/users` | List / create users (role-scoped) |
| GET/POST | `/api/projects` · GET `/api/projects/{id}` | Projects |
| POST | `/api/projects/{id}/master-plan` | Submit plan → AI generates deliverables |
| GET/POST/DELETE | `/api/projects/{id}/files` (+`/{fid}/download`) | Project documents |
| GET/POST/PATCH/DELETE | `/api/projects/{id}/deliverables` | Deliverables |
| POST | `/api/projects/{id}/deliverables/{did}/analyze` | Grok analysis |
| GET/POST/PATCH/DELETE | `/api/projects/{id}/cards` | Dev Kanban |
| GET | `/api/tickets` | Cross-project ticket monitor |
| GET/POST/DELETE | `/api/commercial/boards` (+ `/cards`) | Commercial workspace |
| GET | `/api/projects/{id}/monitoring` | Client monitoring |

Interactive docs: **`/docs`**.
