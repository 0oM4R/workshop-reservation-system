# Workshop Reservations

Browse workshops, reserve a seat with a name and email, and cancel a reservation. Available seats update live in every open browser.

Built with FastAPI, PostgreSQL, and Vue 3 + TypeScript. Nuxt UI runs through Vite; Python dependencies use uv and frontend dependencies use npm. Search uses LangChain with a local embedding model, so it needs no API key.

## Implementation assumptions

- **Upcoming workshops:** this app serves the registration period before a conference. All workshops are expected to be in the future while registration is open; browsing or booking past workshops is outside that workflow.
- **Registration closes before the conference:** the organizer is responsible for closing reservation access before the conference starts. This is an operating assumption, not an automatic feature: the API currently has no conference deadline, date filter, or time-based reservation check. Leaving it accessible after the deadline would still allow bookings when seats remain.
- **Stable catalog during registration:** workshop titles and descriptions are indexed at API startup. Catalog edits require restarting the API to refresh search; seat counts continue to update live without rebuilding the index.

Fresh demo data uses future dates, but reseeding preserves existing dates and reservations. An old demo database can therefore contain past workshops; the upcoming-workshop assumption does not refresh those dates automatically.

## Run with Docker

With Docker and Compose installed, run from the repository root:

```sh
docker compose up --build
```

Open **<http://localhost:8080>**. Compose starts PostgreSQL, applies migrations, seeds 36 demo workshops, and starts the API and nginx frontend. The first build downloads the search model into the API image, so it takes a few minutes. **`migrate exited with code 0` is expected:** its startup work is complete. Only the web service publishes a port.

Try reserving the single seat in **Knife Skills**, then cancel with the same email. Open another browser window to see the count change.

Search above the list, for example "how to make my team ship faster", and switch between hybrid, keyword and semantic ranking. Results keep their live seat counts. The search API is described in [API](docs/api.md).

Stop with Ctrl+C, then `docker compose down`. Data stays in the named volume. **`docker compose down --volumes` deletes all database data.**

## Evaluate search

From the repository root, with Docker and Make installed, run:

```sh
make evaluate
```

Output is shown in the terminal and saved to `eval-results.txt` in the repository root, overwriting the previous report. Evaluation failures still make the command fail.

Without Make, use the equivalent command (requires Bash):

```sh
bash -o pipefail -c 'docker compose --ansi never --progress quiet run --build --rm --no-deps -T \
  api python -u -m app.search.evaluate 2>&1 | tee eval-results.txt'
```

The [evaluation script](backend/app/search/evaluate.py) runs hand-labeled queries against the demo catalog with the real search implementation and embedding model. For keyword, semantic and hybrid search it prints each query's top three workshops, then a summary table. An onnxruntime telemetry warning before the report is harmless.

**Hit@3** is the share of queries with the intended workshop in the first three results. **MRR@10** is the mean reciprocal rank of the intended workshop in the first ten results, zero when absent. Higher is better, up to 100% and 1.

Queries mix exact titles, specific skills, natural-language requests, and requests whose words also appear in other workshops; each has one intended workshop. This is a small, subjective relevance check, not a benchmark: it ignores other relevant workshops, latency and no-match behavior, and has no pass/fail threshold. Only errors exit nonzero.

The index is built from the demo titles and descriptions in seed order, so no database or running stack is needed. The command builds the API image if needed and uses its bundled model offline; the first build needs internet access.

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

## How it stays consistent

- **Capacity:** one transaction inserts the reservation and conditionally increments the seat counter only while space remains. A database CHECK constraint backs up that limit.
- **Duplicates:** a partial unique index allows one active reservation per workshop and case-insensitive email. Retrying returns that reservation; cancelling twice releases only one seat.
- **Live counts:** PostgreSQL publishes seat changes only on commit. Each API process forwards them over SSE; browsers reload the list on reconnect to recover missed changes.

More API workers can share the same PostgreSQL database. Each needs a dedicated listener connection and a proxy that supports long-lived SSE; see the [scaling path](docs/architecture.md#scaling-path).

## Limits

There is no authentication or email verification. **Anyone who knows an email can reserve or cancel with it**, and repeating a reservation reveals its stored name. Before public use, add emailed confirmation links or logins, plus rate limiting. See [deployment requirements](docs/operations.md#deployment-boundary) for HTTPS, credentials, and backups.

## Documentation

- [API](docs/api.md): endpoints, validation, errors, and examples.
- [Architecture](docs/architecture.md): transactions, live updates, and scaling.
- [Contributing](CONTRIBUTING.md): checks, migrations, dependencies, and CI.
- [Operations](docs/operations.md): configuration and troubleshooting.
- [AGENTS.md](AGENTS.md): engineering rules. [TASKS.md](TASKS.md): acceptance checklist.
