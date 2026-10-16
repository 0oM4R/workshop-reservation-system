# Tasks

Work top to bottom. Each task fits in one commit and ends with a check; tick the box only when the check passes. Rules referenced here are in [AGENTS.md](AGENTS.md).

## 1. Foundation

- [x] **1.1 Backend skeleton.** `backend/` managed with uv (`pyproject.toml`, `.python-version`, `uv.lock`); FastAPI app with `GET /api/health`. Check: `uv run uvicorn app.main:app` answers `{"status": "ok"}`.
- [x] **1.2 Settings.** pydantic-settings class (database URL, test database URL, `SEED_DATA`) and `.env.example`. Check: every setting is listed in `.env.example` with a working default.
- [x] **1.3 Backend tooling.** Ruff (including the docstring rules `D` with the Google convention) and pyright configured in `pyproject.toml`; pytest, pytest-asyncio and httpx as dev dependencies; one test for `/api/health`. Check: `uv run ruff check`, `uv run ruff format --check`, `uv run pyright` and `uv run pytest` pass.
- [x] **1.4 Frontend skeleton.** Vue 3 + TypeScript + Vite in `frontend/`, Nuxt UI through its Vite plugin, Vite proxy for `/api` to `localhost:8000`. Check: `npm run dev` shows a page that displays the health response.
- [x] **1.5 Frontend tooling.** ESLint, Prettier, vue-tsc and Vitest, with npm scripts `lint`, `format`, `typecheck`, `test`. Check: `npm run lint`, `npm run typecheck` and `npm run test` pass.
- [x] **1.6 Development database.** `compose.yaml` with `db` only (Postgres, healthcheck, named volume) and an init script that creates `workshops_test`. Check: `docker compose up -d --wait db` reports healthy and both databases exist.
- [x] **1.7 Makefile.** `dev-db`, `lint`, `test`. Check: `make lint` and `make test` run both sides; `make dev-db` starts the database (migrations and seed join in section 2).

## 2. Workshop data

- [x] **2.1 Alembic.** Async `env.py` reading the URL from settings. Check: `uv run alembic upgrade head` runs on an empty database.
- [x] **2.2 Workshops table.** Model and migration: `id`, `slug` (unique), `title`, `starts_at`, `capacity`, `reserved` (default 0), `CHECK (reserved BETWEEN 0 AND capacity)`. Check: a test shows that setting `reserved` above `capacity` fails.
- [x] **2.3 Reservations table.** Model and migration: `id`, `workshop_id`, `name`, `email`, `status` (`active` or `cancelled`), timestamps, and the partial unique index on `(workshop_id, lower(email)) WHERE status = 'active'`. Check: a second active reservation for the same workshop and email in any letter case fails; one after a cancellation succeeds.
- [x] **2.4 Seed script.** `python -m app.seed` inserts about six workshops, one with capacity 1; `ON CONFLICT DO NOTHING` on slug; runs only when `SEED_DATA=true`. Check: running it twice leaves the same rows. `make dev-db` now migrates and seeds.
- [x] **2.5 Test fixtures.** Tests use `workshops_test`, migrate once per session and truncate tables between tests. Check: two tests that insert the same slug both pass.

## 3. List workshops

- [x] **3.1 `GET /api/workshops`.** Returns `id`, `title`, `starts_at`, `capacity` and `remaining`, ordered by start time, with no emails. Check: an integration test asserts the shape and that `remaining = capacity - reserved`.

## 4. Reserve a seat

- [x] **4.1 Request validation.** Name required with a length limit; email valid and trimmed. Check: tests show invalid input returns 422.
- [x] **4.2 `reserve()` in the reservations service.** Insert with the named conflict target, then the conditional `UPDATE`, in one transaction; retry once if the conflicting reservation was cancelled before it could be read. Check: tests for a new reservation, the same email in another letter case, and a full workshop with the counter unchanged.
- [x] **4.3 `POST /api/workshops/{id}/reservations`.** 201 new, 200 existing, 409 full, 404 unknown workshop. Check: one test per status.
- [x] **4.4 Capacity under load.** 50 parallel reserves on a 10-seat workshop. Check: exactly 10 succeed and `reserved = 10`, five runs in a row.
- [x] **4.5 Duplicate burst.** The same email sent 10 times in parallel. Check: one reservation, one 201, the rest 200.

## 5. Cancel a reservation

- [x] **5.1 `cancel()` in the reservations service.** Find the active reservation by workshop and lowercased email, set `status = 'cancelled'`, and decrement `reserved` only if that changed a row. Check: a double cancel decrements once.
- [x] **5.2 `POST /api/workshops/{id}/reservations/cancel`.** Body: the email. Always 200 with the same message, whether the seat was just cancelled, was already cancelled or never existed, so a retried cancel never looks like a failure; 404 only for an unknown workshop. Check: a test for each case.
- [x] **5.3 Counter invariant.** A parallel mix of reserves and cancels. Check: afterwards `reserved` equals the number of active reservations for every workshop.

## 6. Live updates

- [x] **6.1 `Broadcaster` interface and in-process implementation.** One bounded `asyncio.Queue` per subscriber; drop subscribers whose queue is full. Check: unit tests for fan-out and for dropping a slow subscriber.
- [x] **6.2 `GET /api/events`.** sse-starlette with keep-alive pings and cleanup on disconnect. Check: `curl -N localhost:8000/api/events` shows pings, and closing it removes the subscriber.
- [x] **6.3 Publish after commit.** Reserve and cancel publish `{workshop_id, remaining}` only after commit. Check: tests see an event after a new reservation and a cancel, and none after a 409, a repeated reserve or a second cancel.
- [x] **6.4 Postgres LISTEN/NOTIFY broadcaster.** `NOTIFY` inside the transaction; one dedicated asyncpg listener per process that reconnects; the only broadcaster the app runs. Check: the 6.3 tests pass with it, and an event published through one API process reaches a client of another.

## 7. Frontend

- [ ] **7.1 API client and types.** Axios instance with base URL `/api`; hand-written response types in one file. Check: `npm run typecheck` passes.
- [ ] **7.2 `useWorkshops()` composable.** Loads the list with loading and error state. Check: Vitest covers success and failure with Axios mocked.
- [ ] **7.3 Workshop list.** Title, start time and remaining seats, a full state, loading and error states. Check: the seeded workshops show in the dev server.
- [ ] **7.4 Reserve form.** `UForm` with a Zod schema for name and email; the button is disabled while submitting; clear messages for new, already reserved and full. Check: Vitest covers validation, and all three outcomes show in the browser.
- [ ] **7.5 Cancel form.** Asks for the email used to reserve; disabled while the request runs; shows the server's message. Check: cancelling from a different browser raises the remaining count.
- [ ] **7.6 Live updates.** `EventSource` on `/api/events`; load the list in `onopen`; patch `remaining` on each event. Check: Vitest with a mocked `EventSource` updates the right workshop, and two browser windows stay in sync.

## 8. Containers

- [ ] **8.1 API image.** Dockerfile copying uv from its official image and running `uv sync --locked`. Check: `docker compose build api` succeeds.
- [ ] **8.2 `migrate` service.** Same image; runs `alembic upgrade head`, then the seed when `SEED_DATA=true`; `api` waits for it with `service_completed_successfully`. Check: `docker compose up` shows migrate exiting 0 before `api` starts.
- [ ] **8.3 Web image.** Node build stage, then nginx: `try_files $uri /index.html`, `/api/` proxied to `api:8000`, `proxy_buffering off` and a long read timeout on `/api/events`. Check: the page and `/api/workshops` both load through nginx.
- [ ] **8.4 Full stack.** Only `web` publishes a port; every variable has a default. Check: a fresh clone with no `.env` starts with `docker compose up` and lists the seeded workshops.
- [ ] **8.5 SSE smoke test.** pytest against the running stack through nginx: open the stream, reserve, and expect the event within a few seconds. Check: it passes against `docker compose up`.

## 9. CI

- [ ] **9.1 GitHub Actions.** On push and pull request: `make lint`, backend tests with a Postgres service container, frontend tests, and `docker compose build`. Check: all jobs pass on a pull request.

## 10. Documentation

- [ ] **10.1 README.** What the app does, `docker compose up` and the URL, the dev loop, the make targets, how capacity, duplicates and live updates are handled, the scaling path, the known weakness that anyone who knows an email can reserve or cancel with it (fixed in production by an emailed confirmation link or logins, plus rate limiting), and a note that `migrate exited with code 0` is expected. Check: someone new can start the stack from the README alone.
