# TaskFlow — Task Management API

A Django REST Framework API for managing projects and tasks with JWT authentication, background notifications via Celery, Redis-backed caching, and PostgreSQL storage.

---

## Quick Start (Docker — recommended)

```bash
docker-compose up --build
```

This brings up the full stack in one command:
- **Web app** at http://localhost:8000
- **PostgreSQL** database
- **Redis** for caching + Celery broker
- **Celery worker** for background notifications
- **Celery beat** for periodic overdue task checks

### Without Docker (local development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables for PostgreSQL (or skip for SQLite default)
export DB_ENGINE=django.db.backends.postgresql
export DB_NAME=taskflow
export DB_USER=your_user
export DB_PASSWORD=your_password
export DB_HOST=localhost
export DB_PORT=5432
export REDIS_URL=redis://127.0.0.1:6379/1
export CELERY_BROKER_URL=redis://127.0.0.1:6379/0
export CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# 3. Run migrations and start
python manage.py migrate
python manage.py runserver

# 4. Start Celery worker (separate terminal)
celery -A taskflow worker -l info --pool=solo  # --pool=solo required on Windows

# 5. Start Celery beat for periodic overdue checks (separate terminal)
celery -A taskflow beat -l info
```

Without Redis/Celery, the app still works — caching falls back to in-memory, but notifications won't process until Celery is running.

### Run Tests

```bash
python manage.py test --verbosity=2
```

42 tests covering auth, CRUD, authorization boundaries, cache invalidation, and notification triggers.

---

### Key Design Decisions

**JWT Authentication (SimpleJWT)** — Stateless auth scales better for APIs and avoids server-side session storage. Access tokens expire in 1 hour; refresh tokens last 7 days. Passwords are hashed via Django's PBKDF2 (bcrypt available via settings).

**Authorization via Queryset Scoping** — Views filter querysets by `request.user` at the view level. Users only see their own projects/tasks. Unauthorized access returns 404 (not 403), preventing information leaks about resource existence.

**Celery for Background Notifications** — Notification creation is decoupled from the request/response cycle via `shared_task`. Three notification types:
- **Reassignment**: fired when a task's assignee changes
- **Status change**: fired when a task's status changes
- **Overdue**: periodic task (Celery Beat, hourly) scans for past-due tasks

**Redis Caching on Task List** — `GET /tasks/` responses are cached by `user_id + query_params` with a 5-minute TTL. Any task mutation (create/update/delete) invalidates all `task_list:*` keys via `delete_pattern` (Redis) or `cache.clear()` (LocMemCache fallback).

**Metrics Middleware** — Thread-safe in-memory counters track total requests, errors (4xx/5xx), requests by HTTP method, and average response time. Exposed at `GET /metrics/`.

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup/` | Register (username, email, password) |
| POST | `/api/auth/login/` | Get JWT tokens |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| GET | `/api/auth/users/` | List all users (for assignee dropdown) |

### Projects (CRUD)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/projects/` | List your projects |
| POST | `/api/projects/` | Create project |
| GET | `/api/projects/{id}/` | Get project |
| PUT | `/api/projects/{id}/` | Update project |
| DELETE | `/api/projects/{id}/` | Delete project |

### Tasks (CRUD + Filtering + Caching)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks/` | List tasks (paginated, filtered, cached) |
| POST | `/api/tasks/` | Create task |
| GET | `/api/tasks/{id}/` | Get task |
| PUT | `/api/tasks/{id}/` | Update task (triggers notifications) |
| DELETE | `/api/tasks/{id}/` | Delete task |

**Filters:** `?status=todo`, `?assignee=1`, `?due_date_from=2026-01-01`, `?due_date_to=2026-12-31`, `?page=2`

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | List your notifications |
| GET | `/api/notifications/{id}/` | Get notification detail |
| PATCH | `/api/notifications/{id}/` | Mark as read (`{"is_read": true}`) |

### Operational
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health/` | Health check |
| GET | `/metrics/` | Request/error counters, avg response time |

---

## Deployment

**Path chosen: Docker Compose** — `docker-compose up --build` brings up the full stack (app, PostgreSQL, Redis, Celery worker, Celery beat) with a single command.

---

## CI Pipeline

GitHub Actions config at `.github/workflows/ci.yml` runs:
1. **Lint** — flake8 with max line length 120
2. **Test** — full test suite against PostgreSQL + Redis services

---

## Test Suite (42 tests)

| Area | Tests | What's Covered |
|------|-------|----------------|
| Auth | 9 | Signup, login, token refresh, password hashing, duplicate prevention |
| Projects | 8 | CRUD, owner-only access, authorization boundaries |
| Tasks | 11 | CRUD, assignee, cross-project auth, filtering (status/assignee/date range), pagination |
| Cache | 4 | List caching, invalidation on create/update/delete |
| Notifications | 12 | Reassignment, status change, overdue detection, no duplicates, owner fallback, API isolation |

---

## What I'd Do With More Time

### What was prioritized
- **Correctness**: Authorization boundaries, cache invalidation, notification triggers — these are tested thoroughly because bugs here are the most damaging.

### What was deprioritized
- **Database**: SQLite as default for easy local dev; PostgreSQL via environment variables and Docker. In production, I'd add connection pooling (pgbouncer) and proper indexes on `status`, `assignee`, `due_date`.
- **Search**: Currently filter-only (exact match on status/assignee, date range). A full-text search on task title/description via PostgreSQL `SearchVector` or Elasticsearch would be the next step.
- **Frontend**: Simple HTML/JS served by Django templates. Adequate as a demo but not production-grade — would use React/Next.js with proper state management for a real product.
