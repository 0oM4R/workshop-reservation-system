FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

# Readable by the unprivileged user whatever the file modes in the checkout.
COPY --chmod=755 alembic.ini ./
COPY --chmod=755 app ./app
COPY --chmod=755 migrations ./migrations

RUN useradd --system app
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
