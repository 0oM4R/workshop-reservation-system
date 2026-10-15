.PHONY: dev-db lint test

# Migrations and seed join in section 2 of TASKS.md.
dev-db:
	docker compose up -d --wait db

lint:
	cd backend && uv run ruff check && uv run ruff format --check && uv run pyright
	cd frontend && npm run lint && npm run typecheck

test:
	cd backend && uv run pytest
	cd frontend && npm run test
