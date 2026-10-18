FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/app/models

# Dependencies first, so code changes don't invalidate this layer.
# Readable by the unprivileged user, like the files below: `uv add` writes them 0600.
COPY --chmod=644 pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

# Bake in the embedding model so containers never download it. Must match
# EMBEDDING_MODEL in app/search/index.py; HF_HUB_OFFLINE fails startup on mismatch.
# The download leaves some cache files readable by root only.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" \
    && chmod -R a+rX /app/models
ENV HF_HUB_OFFLINE=1

# Readable by the unprivileged user whatever the file modes in the checkout.
COPY --chmod=755 alembic.ini ./
COPY --chmod=755 app ./app
COPY --chmod=755 migrations ./migrations

RUN useradd --system app
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
