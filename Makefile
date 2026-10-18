.PHONY: deps dev-db dev-api dev-web lint test evaluate

deps:
	cd backend && uv sync --locked
	cd frontend && npm ci

dev-db:
	docker compose -f compose.yaml -f compose.dev.yaml up -d --wait db
	cd backend && uv run alembic upgrade head && uv run python -m app.seed

# The API on :8000 with reload, after the database is up, migrated and seeded.
dev-api: dev-db
	cd backend && uv run uvicorn app.main:app --reload

# The Vite dev server; it proxies /api to the API on :8000.
dev-web:
	cd frontend && npm run dev

lint:
	cd backend && uv run ruff check && uv run ruff format --check && uv run pyright
	cd frontend && npm run lint && npm run typecheck

test:
	cd backend && uv run pytest
	cd frontend && npm run test

evaluate:
	bash -o pipefail -c 'docker compose --ansi never --progress quiet run --build --rm --no-deps -T \
		api python -u -m app.search.evaluate 2>&1 | tee eval-results.txt'
