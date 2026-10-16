# Workshop Reservations

Browse workshops and their remaining seats, reserve a seat with a name and email, and cancel a reservation. Seat counts update live in every open browser.

## Guarantees

These hold under any load and drive most of the design below.

- Capacity is never exceeded, however many requests arrive at once.
- Retries, timeouts and double submits never create duplicate reservations.
- Every change reaches all open clients promptly.
- `docker compose up` starts the whole stack; running it needs nothing but Docker.

## Stack

- **Backend:** Python (version in `backend/.python-version`), FastAPI, SQLAlchemy 2.0 async on asyncpg, Alembic, pydantic-settings, sse-starlette. Managed with uv.
- **Frontend:** Vue 3, TypeScript, Vite, Nuxt UI through its Vite plugin (not the Nuxt framework), Axios, Zod. Managed with npm.
- **Database:** PostgreSQL.
- **Quality:** Ruff, pyright, pytest (pytest-asyncio, httpx); ESLint, Prettier, vue-tsc, Vitest. CI is GitHub Actions on every push and pull request.

## Layout

- `backend/`: the API (`app/`), Alembic migrations, tests
- `frontend/`: the Vue app and the nginx config for the `web` image
- `compose.yaml`: `db`, `migrate` (runs migrations and the seed script, then exits 0), `api`, and `web` (nginx serving the built frontend and proxying `/api/*` to `api`). Only `web` publishes a port.
- `Makefile`: `dev-db`, `lint`, `test`
- `.env.example`: every configuration variable

## Commands

```sh
make dev-db                                          # Postgres in Docker, migrated and seeded; also creates workshops_test
cd backend && uv run uvicorn app.main:app --reload   # API on :8000
cd frontend && npm run dev                           # Vite dev server; proxies /api to :8000
make lint                                            # Ruff, pyright, ESLint, Prettier, vue-tsc
make test                                            # pytest (needs make dev-db) and Vitest
docker compose up --build                            # full stack through nginx
```

Run `make lint` and `make test` before calling a change done; CI runs the same targets.

Work through [TASKS.md](TASKS.md) in order, and tick a task only when its check passes.

## Coding rules

- Never commit, push or rewrite git history. Leave changes uncommitted for a human to review.
- Make the smallest change that solves the problem. No speculative abstractions, options or config; don't refactor unrelated code in the same change.
- Prefer readable over clever: descriptive names, small single-purpose functions, early returns instead of deep nesting, named constants instead of magic numbers.
- Keep layers separate. Routes validate input, call a service and map the result to a response; SQL and transactions live in services; Vue components only display and delegate, with logic in composables.
- Extract shared code once duplication is real, not in advance.
- Handle errors explicitly. No bare `except` or swallowed errors; map domain outcomes to HTTP status codes in one place.
- Comments explain why, not what. Delete dead code instead of commenting it out.
- Formatting is decided by Ruff and Prettier; otherwise match the surrounding code.

### Docstrings

- **Python:** PEP 257 with the Google style, enforced by Ruff's `D` rules. Every module, public class and public function gets one. The first line is a short imperative summary ending in a period. Add `Args:`, `Returns:` or `Raises:` only when the signature and name don't already make it clear.
- **TypeScript and Vue:** a short `/** ... */` comment on exported functions, composables and types, following the same one-line summary rule.

```python
async def reserve(session: AsyncSession, workshop_id: int, name: str, email: str) -> ReserveResult:
    """Reserve one seat, or return the active reservation this email already holds.

    Raises:
        WorkshopNotFound: If no workshop has this id.
    """
```

## Reservations: rules that must not break

Reserving is one transaction, in this order:

1. `INSERT INTO reservations ... ON CONFLICT (workshop_id, lower(email)) WHERE status = 'active' DO NOTHING RETURNING id`
   - No row returned: that email already holds a seat. Return the existing reservation with 200. If it was cancelled before you could read it, retry once.
2. `UPDATE workshops SET reserved = reserved + 1 WHERE id = :id AND reserved < capacity RETURNING reserved, capacity`
   - Row returned: commit and return 201. No row: roll back and return 409 (full).

- Never check seats in Python and then write. The conditional `UPDATE` is the only gate; `CHECK (reserved BETWEEN 0 AND capacity)` is the backstop.
- Always name the conflict target. A bare `ON CONFLICT DO NOTHING` also swallows unrelated unique violations.
- Insert before incrementing, so a seat is never taken without a reservation row.
- Cancelling sets `status = 'cancelled'` only `WHERE status = 'active'`, and decrements `reserved` only if that changed a row. Cancelling twice is harmless.
- Every write to `reserved` goes through the reservations service. `reserved` always equals the number of active reservations.

## Live updates

- Publish only after the transaction commits: the seat `UPDATE` queues the `NOTIFY` with `pg_notify` in its `RETURNING`, and Postgres sends it on commit and drops it on rollback. Never publish from Python.
- SSE clients subscribe through the `Broadcaster` interface. The app runs the Postgres LISTEN/NOTIFY implementation; the in-process one fans out to each process's clients and is the test fake.
- The payload is `{workshop_id, remaining}` only (NOTIFY payloads are capped at 8 KB). Clients re-fetch the list on every connect and reconnect.
- The LISTEN connection is a dedicated asyncpg connection with a plain `postgresql://` URL, never taken from the SQLAlchemy pool, and it reconnects on failure.
- Each SSE client gets a bounded `asyncio.Queue`; drop clients that fall behind.
- nginx needs `proxy_buffering off` and a long `proxy_read_timeout` on `/api/events`.

## API

- All routes live under `/api`; nginx and the Vite proxy forward the path unchanged. The SSE stream is `GET /api/events`.
- Validate every input server-side with Pydantic. Frontend validation is only for feedback.
- Responses expose `remaining` seats and never include other people's emails. Emails are trimmed and compared case-insensitively.
- Cancelling is `POST /api/workshops/{id}/reservations/cancel` with the email used to reserve. For a known workshop it always returns 200 with the same message, so a retried cancel never looks like a failure; an unknown workshop returns 404. No endpoint lists reservations by email.

## Database and migrations

- Never edit a merged migration; add a new one. Autogenerate can miss CHECK constraints and expression or partial indexes, so review every generated file.
- Migrations hold the schema and required reference data. Demo data lives in the seed script (`python -m app.seed`), runs only when `SEED_DATA=true`, and is safe to rerun (`ON CONFLICT DO NOTHING` on a fixed slug).

## Testing

- Backend tests run against real Postgres (`workshops_test`). Never mock the database or use SQLite: the guarantees live in SQL (the conditional UPDATE, the partial unique index, row locks, NOTIFY on commit).
- Truncate tables between tests. Don't roll back per-test transactions; concurrency tests need separate connections and committed data.
- Changes to reserving, cancelling or events need tests that prove: parallel reserves never exceed capacity; a repeated email gives one reservation and a 200; a full workshop returns 409 with the counter unchanged; a double cancel decrements once; `reserved` equals active reservations after a burst; events fire only after commit.
- The SSE smoke test runs against the full Compose stack through nginx, not in-process.
- Frontend unit tests (Vitest) mock Axios and `EventSource`.

## Frontend

- One page. Server state lives in the `useWorkshops()` composable built on Vue refs; no Pinia, Vue Router or query library.
- The composable loads the list on connect, so it shows even when the stream is down, and again in `EventSource`'s `onopen`, which resyncs after every reconnect. It patches `remaining` on each event, and reopens the stream itself when the browser gives up after an HTTP error.
- `remaining` changes only from a list load or a stream event, never from a reserve response: the stream delivers changes in commit order, and a response can arrive after a newer event. While the stream is down, a successful reserve or cancel reloads the list instead.
- Disable Reserve and Cancel while a request is in flight.
- Forms use Nuxt UI's `UForm` with a Zod schema. API response types are hand-written in one file.

## Conventions

- Configuration comes from pydantic-settings; never read `os.environ` directly. A new variable goes in the settings class, in `.env.example`, and as a default in `compose.yaml`, so `docker compose up` works without a `.env`.
- Add dependencies with `uv add` and `npm install`; commit `uv.lock` and `package-lock.json`.
- Type hints everywhere in Python; no synchronous database calls in request handlers.
- Never commit secrets or a `.env` file.
