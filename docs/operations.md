# Operations and troubleshooting

[README](../README.md) · [Architecture](architecture.md) · [API](api.md) · [Contributing](../CONTRIBUTING.md)

## Configuration

[Settings](../backend/app/settings.py) reads process environment variables. No `.env` file is loaded.

| Variable            | Local default                                                            | Used by                         |
| ------------------- | ------------------------------------------------------------------------ | ------------------------------- |
| `DATABASE_URL`      | `postgresql+asyncpg://workshops:workshops@localhost:5432/workshops`      | API, migrations, seed, listener |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://workshops:workshops@localhost:5432/workshops_test` | Backend tests                   |

Compose sets `DATABASE_URL` to use host `db`. The checked-in credentials are for local development. The frontend uses `/api` through nginx or Vite and needs no environment variables. Addresses are in the [setup instructions](../README.md#run-with-docker).

The API image also sets `FASTEMBED_CACHE_PATH=/app/models`, where the search models are stored at build time, and `HF_HUB_OFFLINE=1`, so containers never download them. In host development, the first API start downloads the models (about 150 MB) into the system temp folder.

## Startup, shutdown, and persistence

Start the stack using the [README](../README.md#run-with-docker), then inspect it with:

```sh
docker compose ps -a
docker compose logs --tail=100 migrate api db web
curl --fail http://localhost:8080/api/workshops
```

`docker compose down` retains the named `db-data` volume. **Adding `--volumes` deletes the database and all reservations.** Normal restarts and [reseeding](../CONTRIBUTING.md#schema-and-demo-data) need no reset.

The Postgres init script creates `workshops_test` only on first volume initialization. If that database is missing, create it while `db` is running:

```sh
docker compose exec db psql -U workshops -d workshops \
  -c 'CREATE DATABASE workshops_test OWNER workshops;'
```

Then run `make dev-db` and `make test`. Tests rebuild the test schema; never point `TEST_DATABASE_URL` at valuable data.

## Diagnose common failures

| Symptom                                | Check and action                                                                                                                                        |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cannot connect to Docker               | Start the Docker daemon; check `docker info`.                                                                                                           |
| Port 8080, 5432, or 8000 is busy       | Stop the conflicting stack or local service. For Vite, use its printed URL.                                                                             |
| Stack fails to start                   | Inspect `docker compose ps -a` and logs, especially `migrate`. Preserve the volume while diagnosing.                                                    |
| Host API/tests cannot reach PostgreSQL | Run `make dev-db` to publish port 5432; check the configured database URL.                                                                              |
| No workshops or old dates              | Check seed output. Reseeding inserts missing slugs but preserves existing dates.                                                                        |
| Counts stop updating                   | Open `curl -N http://localhost:8080/api/events`, wait for a ping, then reserve. Check API logs for LISTEN failures. Use port 8000 for host development. |
| API docs do not open                   | In host development, visit `http://localhost:8000/docs`; the proxies forward only `/api`.                                                               |
| Health is OK but requests fail         | `/api/health` checks HTTP liveness only. Check `/api/workshops`, API logs, and the event stream.                                                        |
| A submission times out                 | It may have committed. Retry with the same workshop and email after the ten-second timeout.                                                             |
| API exits at startup loading a model   | In Compose, rebuild with `docker compose build api`: the image holds the models and never downloads them. Host development downloads them once, online. |

## Deployment boundary

This Compose stack is intended for local demonstration, not public deployment.
