# Task Management GraphQL API

A GraphQL API (Strawberry, code-first) for managing tasks within projects. Python 3.12, async
SQLAlchemy + asyncpg, Alembic migrations, Postgres, Starlette/Uvicorn.

## Running it

### Docker Compose (recommended)

```bash
docker compose up --build
```

Starts Postgres, runs migrations, and serves the API at `http://localhost:8000/graphql`
(GraphiQL enabled). Optionally seed demo data: `docker compose exec api python -m taskmanager.scripts.seed`.

### Locally, via `uv`

```bash
uv sync
cp .env.example .env   # point DATABASE_URL at your Postgres (14+)
uv run alembic upgrade head
uv run python -m taskmanager.scripts.seed   # optional demo data
uv run uvicorn taskmanager.main:app --reload
```

### Auth

Requests are stubbed as an authenticated user via an `X-User-Id: <int>` header. No header means
anonymous, read-only access.

### Tests

```bash
uv run pytest
```

Needs its own Postgres database (`TEST_DATABASE_URL`); runs the real Alembic migrations once per
session. 34 tests covering concurrency, N+1 query counts, authorization, pagination, and validation.

## Key decisions

- **Postgres + SQLAlchemy 2.0 async + Alembic**, not SQLite — the concurrency requirement needs
  real multi-connection transactional semantics.
- **Starlette, not FastAPI** — the brief asks for an ASGI server, not a REST framework; FastAPI's
  own validation layer would just duplicate Pydantic.
- **Manual Pydantic validation** (`domain/schemas.py`) rather than `strawberry.experimental.pydantic`,
  which is explicitly experimental.
- **Cursor (keyset) pagination**, not offset — `OFFSET` degrades and shifts under concurrent writes
  at the scale ("thousands of tasks") the brief calls out. `projectId` is required since every
  index is project-scoped. Four sort options (newest first, status, priority, assignee), each a
  fixed direction rather than exposing independent asc/desc per field.
- **Optimistic concurrency** via a `version` column — every mutation is a single conditional
  `UPDATE ... WHERE id = :id AND version = :expected`. A conflict returns a typed
  `TaskConflictError` rather than blocking or silently overwriting. See `services/tasks.py`.
- **DataLoaders for all relationships**, built fresh per request. Models have FK columns only, no
  ORM `relationship()` — DataLoader is the only path to related data, so N+1 isn't just avoided
  once, it's structurally not possible. See `tests/integration/test_n_plus_one.py`.
- **Auth**: `X-User-Id` header resolved once per request. Any authenticated user can
  create/update/change-status/assign; **delete** is the one access-controlled action, restricted
  to a task's creator, its assignee, or the project owner.
- **Typed error unions per mutation** (e.g. `Task | ValidationError | TaskConflictError`) for
  expected/domain outcomes, so clients handle them via `... on TaskConflictError {}`. Unexpected
  exceptions are masked by a schema extension — no stack traces or bare 500s reach the client.
- **One `AsyncSession` per unit of work**, not one per request — `AsyncSession` isn't safe across
  concurrent coroutines, and DataLoader batching creates exactly that within a request.

## Deliberately left out

- Project membership / roles — authorization is limited to the one delete rule above.
- Status transition rules — `changeTaskStatus` allows any transition.
- Cross-project task listing (every index is project-scoped).
- Bonus features (rate limiting, structured logging, bulk/idempotent mutations) — the brief says
  not to trade these off against the core, so time went to concurrency/N+1/pagination instead.

## With more time

- Structured request logging (the natural next step given the typed domain errors) or rate limiting.
- A status transition graph, enforced server-side.
- Project membership as a real relation, extending delete/update authorization to it.
- Idempotency keys on `createTask`.
