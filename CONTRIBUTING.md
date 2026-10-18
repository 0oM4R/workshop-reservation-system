# Contributing

Follow the [local setup](README.md#develop-locally) and [engineering rules](AGENTS.md). Work through [TASKS.md](TASKS.md) in order; tick a task only after its check passes. Automated agents must leave changes uncommitted for review.

## Checks

After [local setup](README.md#develop-locally), run from the repository root:

```sh
make lint
make test
```

Backend tests use real PostgreSQL, separate connections, and committed transactions to exercise constraints, locks, and notifications. They rebuild the schema and truncate tables at `TEST_DATABASE_URL`, which defaults to `workshops_test`. **That database must be disposable.** Frontend tests mock Axios and EventSource.

For reservation, cancellation, or event changes, cover the [required concurrency and commit checks](AGENTS.md#testing). For live-update changes, also check two browser windows and run the smoke test through nginx:

```sh
docker compose up -d --build --wait
(cd backend && uv run pytest smoke)
```

The [CI workflow](.github/workflows/ci.yml) runs on every pull request and push to `development`: lint, backend tests with PostgreSQL, frontend tests, and SSE and search smoke tests through the Compose stack.

## Schema and demo data

Follow the [migration rules](AGENTS.md#database-and-migrations). Demo workshops live in [seed.py](backend/app/seed.py), run by both `make dev-db` and Compose's `migrate` service. Reseeding inserts missing slugs and updates existing descriptions while preserving reservations, capacities, and dates.

See [configuration](docs/operations.md#configuration) for database settings.
