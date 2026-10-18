# Workshop Reservations

Browse workshops, reserve a seat with a name and email, and cancel a reservation. Available seats update live in every open browser.

Built with FastAPI, PostgreSQL, and Vue 3 + TypeScript. Nuxt UI runs through Vite; Python dependencies use uv and frontend dependencies use npm. Search uses LangChain with a local embedding model and a local reranking model, so it needs no API key.

## Run with Docker

With Docker and Compose installed, run from the repository root:

```sh
docker compose up --build
```

Open **<http://localhost:8080>**. Compose starts PostgreSQL, applies migrations, seeds 36 demo workshops, and starts the API and nginx frontend. The first build downloads the search models into the API image, so it takes a few minutes. **`migrate exited with code 0` is expected:** its startup work is complete. Only the web service publishes a port.

Try reserving the single seat in **Knife Skills**, then cancel with the same email. Open another browser window to see the count change.

Search above the list, for example "how to make my team ship faster", and switch between hybrid, hybrid + rerank, keyword and semantic ranking. Results keep their live seat counts. The search API is described in [API](docs/api.md).

Stop with Ctrl+C, then `docker compose down`. Data stays in the named volume. **`docker compose down --volumes` deletes all database data.**

## How it stays consistent

- **Capacity:** one transaction inserts the reservation and conditionally increments the seat counter only while space remains. A database CHECK constraint backs up that limit.
- **Duplicates:** a partial unique index allows one active reservation per workshop and case-insensitive email. Retrying returns that reservation; cancelling twice releases only one seat.
- **Live counts:** PostgreSQL publishes seat changes only on commit. Each API process forwards them over SSE; browsers reload the list on reconnect to recover missed changes.

More API workers can share the same PostgreSQL database. Each needs a dedicated listener connection and a proxy that supports long-lived SSE; see the [scaling path](docs/architecture.md#scaling-path).

## Evaluate search

From the repository root, with Docker and Make installed, run:

```sh
make evaluate
```

The [evaluation script](backend/app/search/evaluate.py) tests hand-labeled queries against the demo catalog with the real models. It prints each query's top three results and a summary, also saved to `eval-results.txt` (overwritten each run). No database or running stack is needed; the first image build needs internet access. The underlying Docker command is in the [Makefile](Makefile).

**Hit@3** is the share of queries with the intended workshop in the first three results. **MRR@10** is the mean reciprocal rank of the intended workshop in the first ten results, zero when absent. Higher is better, up to 100% and 1.

Recorded results from 2026-10-18, using 20 queries and 36 demo workshops:

| Mode            |  Hit@3 | MRR@10 |
| --------------- | -----: | -----: |
| Keyword         |  80.0% |  0.800 |
| Semantic        | 100.0% |  0.925 |
| Hybrid          |  90.0% |  0.867 |
| Hybrid + rerank | 100.0% |  1.000 |

Queries cover titles, skills, natural-language requests, and overlapping topics, with one intended workshop each. This small, subjective check excludes other relevant results, latency, and no-match behavior. Scores have no pass/fail threshold; only execution errors fail the command.

## Develop locally

Install Docker, uv, Node.js 22 (used in CI), npm, and Make. uv selects Python from [backend/.python-version](backend/.python-version).

```sh
(cd backend && uv sync --locked)
(cd frontend && npm ci)
make dev-api
```

`make dev-api` starts PostgreSQL on `127.0.0.1:5432`, migrates and seeds it, then runs the API on port 8000 with reload. In a second terminal:

```sh
make dev-web
```

Open the URL printed by Vite, normally <http://localhost:5173>. Vite proxies `/api` to the API. Interactive API docs are at <http://localhost:8000/docs>. No `.env` file is needed or loaded.

## Commands

Run these from the repository root:

| Command                               | Purpose                                                         |
| ------------------------------------- | --------------------------------------------------------------- |
| `make dev-db`                         | Start the development database, migrate, and seed               |
| `make dev-api`                        | Run `dev-db`, then start the API with reload                    |
| `make dev-web`                        | Start Vite                                                      |
| `make lint`                           | Run Python and frontend lint, formatting, and type checks       |
| `make test`                           | Run pytest against PostgreSQL, then Vitest; needs `make dev-db` |
| `make evaluate`                       | Evaluate search relevance in Docker; no running stack needed    |
| `docker compose up --build`           | Build and run the full stack on port 8080                       |
| `(cd backend && uv run pytest smoke)` | Test SSE and search through nginx; needs the full stack running |

Backend tests rebuild and truncate the database at `TEST_DATABASE_URL` (default: `workshops_test`). **Never point it at data you want to keep.**

## Limits

- **Identity:** there is no authentication or email verification. Anyone who knows an email can reserve or cancel with it, and repeating a reservation reveals its stored name. Public use needs confirmation links or logins and rate limiting; see [deployment boundary](docs/operations.md#deployment-boundary).
- **Registration period:** organizers must close access before the conference. The API does not filter past workshops or enforce deadlines. Fresh demo dates are in the future; reseeding preserves existing dates and reservations.
- **Catalog changes:** search indexes titles and descriptions at startup. Restart the API after editing them; seat counts update live independently.

## Documentation

- [API](docs/api.md): endpoints, validation, errors, and examples.
- [Architecture](docs/architecture.md): transactions, live updates, and scaling.
- [Contributing](CONTRIBUTING.md): development checks and demo data.
- [Operations](docs/operations.md): configuration and troubleshooting.

Internal development records: [AGENTS.md](AGENTS.md) contains engineering rules; [TASKS.md](TASKS.md) records the implementation stages and their acceptance checks.
