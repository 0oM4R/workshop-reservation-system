# Technical decisions

These are the technical decisions, the options I compared, and what I assumed. The guiding idea: let PostgreSQL enforce the hard rules, and keep everything else small. [architecture.md](architecture.md) and [api.md](api.md) explain how it works in detail.

## Reservation correctness

### Database

I chose PostgreSQL because the hard rules map to its built-in features: `UPDATE … RETURNING`, partial unique indexes, CHECK constraints, and LISTEN/NOTIFY. It's also the database I know best.

The tradeoff is running a database service. SQLite allows multiple processes to share a database, but only one can write at a time. PostgreSQL better fits concurrent writes and provides the notification mechanism this app needs. MySQL would need workarounds for the partial index and `RETURNING` queries, plus a separate notification mechanism.

### Capacity enforcement

Each reservation uses a conditional `UPDATE` to increment `reserved` only when capacity remains (`WHERE reserved < capacity`). A CHECK constraint provides a backstop. This keeps the capacity check and increment in one statement, with a short lock enforced by the database.

The tradeoff is maintaining a counter: reserving and cancelling must update it in the same transaction as the reservation row. Locking the workshop with `SELECT … FOR UPDATE`, then counting reservations, adds queries and requires every booking path to take the lock. SERIALIZABLE isolation requires handling serialization failures with retries. Advisory or application locks also depend on every code path using them, and an `asyncio.Lock` cannot coordinate separate API processes.

### Duplicate reservations

An insert with `ON CONFLICT` targets the one-active-seat-per-email index. A repeated request returns 200 with the existing active reservation, so a retry succeeds without taking another seat.

This uses the workshop and email as the booking identity. Returning a conflict error for a uniqueness violation would make a successful retry look like a failure. An `Idempotency-Key` design would add request tracking, expiry cleanup, and handling for in-flight duplicates. This app only deduplicates active bookings by workshop and email, so a retry that arrives after a cancellation books a new seat.

### Cancellation

Cancellation uses the workshop and email and returns 200 for a known workshop, including repeated cancellations. It works from another device without storing a reservation id in the browser.

The tradeoff is that knowing an email is enough to cancel its reservation. A browser-only id would prevent cancellation from another device, and using the reservation id as a cancel-link secret would not help while a repeated reserve returns that id to anyone who supplies the email. Email confirmation or login is a production follow-up.

## Live updates

### Browser transport

SSE fits the one-way flow of seat updates and gives the browser automatic reconnection. WebSocket's two-way communication is unnecessary here and would need reconnect handling; polling adds delay and repeatedly fetches unchanged data.

The stream has no durable replay. Clients reload the list when they connect or reconnect to recover missed changes.

### Fan-out across API processes

Postgres LISTEN/NOTIFY distributes changes to every listening API process without another service. The seat `UPDATE` queues the notification itself, so it is delivered only on commit and discarded on rollback.

The in-process broadcaster, built first, remains the local fan-out and test fake; alone, it cannot reach clients attached to other processes. Redis pub/sub adds another service, and publishing from application code after commit leaves a crash window between the two operations. Debezium and Kafka add more infrastructure than this app needs.

Notifications are best effort. A failed database listener reconnects and closes local streams so browsers reconnect and reload the list. This recovery does not provide an event history.

## Application stack

### API framework

FastAPI's async model suits long-lived SSE connections, and type hints support validation and API documentation. Django's broader feature set adds little to this small API; Flask's synchronous request model is a less natural fit for long-lived streams. I preferred FastAPI's ecosystem and examples over Litestar's.

### Data access

SQLAlchemy 2.0 keeps queries close to SQL and provides typed models; Alembic manages migrations. The tradeoff is maintaining separate table models and response schemas, but those shapes differ here anyway, so SQLModel would save little. Raw asyncpg would leave more row mapping and migration tooling to assemble.

### Frontend

Vue 3, TypeScript, and Nuxt UI support a single page with `useWorkshops()` and `useSearch()` composables. Vue lets this app update a reactive workshop's `remaining` field directly. The equivalent React state update creates a new array and copies the changed workshop object.

There is no store, router, or query library. TanStack Query, Pinia, and Vue Router would add concepts to manage one list on one page; the composables handle loading, search, and live updates themselves.

## Search

### In-memory indexing

LangChain combines BM25 keyword retrieval with FastEmbed (`bge-small-en-v1.5`) semantic retrieval. The 36 demo workshops fit in memory, so search needs no extra container.

The tradeoff is rebuilding the index at startup and restarting the API after catalog edits. Qdrant adds a service to configure and maintain and is an option if the in-memory index becomes a bottleneck. pgvector with PostgreSQL full-text search would require an image change and migration, and `ts_rank` does not account for word rarity as BM25 does.

### Hybrid fusion

A small reciprocal rank fusion implementation combines the keyword and semantic rankings while keeping each list's rank visible. LangChain's `EnsembleRetriever` would require the legacy langchain-classic package and does not return scores. The tradeoff is owning this small piece of ranking logic.

### Reranking

A MiniLM-L6 cross-encoder provides a fourth mode, reordering hybrid's top 10 results. Hybrid lost to semantic search on common words such as "make"; the reranker reads the query and each candidate text together.

On the [small demo benchmark of 20 queries](../backend/app/search/evaluate.py), reranking lifted hybrid from Hit@3 90% and MRR@10 0.87 to 100% and 1.0. These results describe this query set, not general search quality.

Reranking adds model inference work. The smallest model ranked the expected workshop first on all 20 demo queries, so I did not choose larger models such as MiniLM-L12 or bge-reranker-base. LangChain's `CrossEncoderReranker` would require langchain-classic, and FlashRank would add another dependency.

## Delivery and quality

### Serving

An nginx container serves the frontend and forwards `/api` on the same origin. Only nginx publishes a port, avoiding a separate frontend API origin and its CORS configuration.

This adds a web-server container but keeps the frontend and API builds separate. Serving the frontend from FastAPI would couple those builds; separate origins would need CORS handling and an API URL per environment.

### Migrations and seed data

A one-off `migrate` container runs migrations and the seed script before the API starts. This makes setup its own step instead of mixing it into each API process's startup.

Demo data stays in a separate seed script that production can skip. Putting it in a migration would couple schema changes to demo content. The tradeoff is coordinating the setup step with API startup, which Compose handles.

### Package management

uv manages Python packages and npm manages frontend packages, both installing from lockfiles. uv keeps Python dependency installation fast; npm is sufficient for this frontend's size.

Poetry would need either Poetry in the image or an extra export step to requirements for pip; uv locks and installs with one tool. A bare `requirements.txt` would need additional conventions for reproducible locking, and pnpm's gains do not justify switching this small project.

### Testing

Integration tests run against real PostgreSQL because capacity enforcement, uniqueness, locks, and notifications live in the database. An API-level SSE smoke test runs through nginx to cover the deployed request path.

The tradeoff is needing PostgreSQL for backend tests. Mocking it would test assumptions about the database instead of its behavior. Browser end-to-end coverage remains a gap: Playwright adds browser tooling and test maintenance, while Cypress's multi-window limitation does not fit the proposed two-window check. One Playwright test is a next step.

### Code quality and CI

Ruff, pyright, ESLint, Prettier, vue-tsc, and Vitest run in GitHub Actions on every pull request and every push to `development`.

Ruff covers the jobs otherwise split across Black, flake8, and isort. pyright keeps type checking aligned with the editor. ESLint and Prettier are the standard Vue toolchain; Biome's Vue support is still partial. The tradeoff is maintaining separate Python and frontend checks.

## Assumptions

These shaped what I built and what I left out.

- **Workshops are upcoming events.** The seed dates every workshop relative to today, so a fresh database only holds future workshops. There is no endpoint to create or edit workshops.
- **Booking closes before a workshop starts.** I assume reservations are closed before each workshop's start time, so a workshop is never in the past while still open for booking. Because of that, the app does not handle past workshops: it neither hides them nor blocks reserving them. If needed, that is a filter on the list query and a start-time check in reserve.
- **The email is the identity.** There is no login, so each email can hold one active seat per workshop, compared case-insensitively. Anyone who knows an email can reserve or cancel in its name.
- **One seat per reservation.** No group bookings, waitlist or payments.
- **The catalog is small.** The list returns every workshop in one response, without pagination (36 in the demo). The search index fits in memory and is built at startup, so edited workshops need an API restart.
- **Live updates are best effort.** Events are not stored. A browser that reconnects reloads the list to catch up.

## Known limits and next steps

These are known gaps I chose not to build, to keep the app small.

- **Reserving or cancelling for someone else's email.** Repeating a reservation also shows the name stored with it. Production fix: a confirmation email with a cancel link, or logins, plus rate limiting.
- **Hand-written frontend types** can drift from the API. Fix: generate them from FastAPI's OpenAPI schema and check in CI.
- **No browser end-to-end test.** Next step: one Playwright test with two windows.
- **Scale.** Measure bottlenecks before adding infrastructure. Consider keyset pagination if list responses become too large, Qdrant if the in-memory search index becomes a bottleneck, or Redis if notification fan-out becomes one. LISTEN/NOTIFY already supports multiple API processes.
- **Production basics** not covered: HTTPS, real secrets, backups, monitoring, a heartbeat on the LISTEN connection, and a retention policy for names and emails.
