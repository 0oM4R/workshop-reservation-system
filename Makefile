.PHONY: dev-db lint test

dev-db:
	docker compose -f compose.yaml -f compose.dev.yaml up -d --wait db
	cd backend && uv run alembic upgrade head && uv run python -m app.seed

lint:
	cd backend && uv run ruff check && uv run ruff format --check && uv run pyright
	cd frontend && npm run lint && npm run typecheck

test:
	cd backend && uv run pytest
	cd frontend && npm run test
