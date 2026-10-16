# Contributing

Follow the [local setup](README.md#develop-locally) and [engineering rules](AGENTS.md). Work through [TASKS.md](TASKS.md) in order; tick a task only after its check passes. Automated agents must leave changes uncommitted for review.

## Checks

Before calling a change done:

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

The [CI workflow](.github/workflows/ci.yml) runs on every pull request and push to `development`: lint, backend tests with PostgreSQL, frontend tests, and the Compose stack with the SSE smoke test.

## Schema and demo data

After editing a model, create a new migration from `backend/`:

```sh
uv run alembic revision --autogenerate -m "describe the schema change"
uv run alembic upgrade head
```

Review generated migrations: CHECK constraints and expression or partial indexes may need explicit operations. Never edit a merged migration. Test against a disposable database; downgrades can discard data.

Migrations contain schema and required reference data. Demo workshops live in [seed.py](backend/app/seed.py). Both `make dev-db` and Compose's `migrate` service run it. To run it manually against the host development database:

```sh
(cd backend && uv run python -m app.seed)
```

Existing slugs are skipped, so rerunning preserves reservations, capacities, and dates.

## Dependencies and configuration

Use `uv add PACKAGE` in `backend/` or `npm install PACKAGE` in `frontend/`; use `--dev` or `--save-dev` for development dependencies. Include the manifest and lockfile changes in the review. Reproducible installs use `uv sync --locked` and `npm ci`. CI uses `npm ci --ignore-scripts` to skip lifecycle scripts, including Git hook installation.

Define settings in [Settings](backend/app/settings.py) with local defaults, document them in [operations](docs/operations.md#configuration), and add container values to Compose when needed. Settings come from process environment variables; no `.env` file is loaded. Never commit secrets.

## Keep docs current

Update [API](docs/api.md) and frontend response types when routes change; [README](README.md) and [operations](docs/operations.md) when setup changes; [architecture](docs/architecture.md) when transaction or recovery behavior changes. Verify documented commands and use fictional personal data in examples.
