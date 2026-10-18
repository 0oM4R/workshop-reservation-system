# Operations and troubleshooting

[README](../README.md) · [Architecture](architecture.md) · [API](api.md) · [Contributing](../CONTRIBUTING.md)

## Configuration

[Settings](../backend/app/settings.py) reads process environment variables. No `.env` file is loaded.

| Variable            | Local default                                                            | Used by                         |
| ------------------- | ------------------------------------------------------------------------ | ------------------------------- |
| `DATABASE_URL`      | `postgresql+asyncpg://workshops:workshops@localhost:5432/workshops`      | API, migrations, seed, listener |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://workshops:workshops@localhost:5432/workshops_test` | Backend tests                   |

Compose sets `DATABASE_URL` to use host `db`. The listener derives a plain `postgresql://` URL for its dedicated asyncpg connection. The checked-in database credentials are for local development.

| Entry point               | Address                                                      |
| ------------------------- | ------------------------------------------------------------ |
| Full stack                | `http://localhost:8080`                                      |
| Host development frontend | Vite's printed URL, normally `http://localhost:5173`         |
| Host development API      | `http://localhost:8000`                                      |
| Host PostgreSQL           | `127.0.0.1:5432`, published only by the development override |

The frontend needs no environment variables: it uses `/api` and `/api/events` through nginx or Vite.

## Startup, shutdown, and persistence

For startup commands, see the [README](../README.md). Compose runs `db` → `migrate` → `api` → `web`. **`migrate` exiting with code 0 means success.** It applies migrations and seeds missing demo workshops before the API starts.

Inspect the stack with:

```sh
docker compose ps -a
docker compose logs --tail=100 migrate api db web
curl --fail http://localhost:8080/api/workshops
```

`docker compose down` retains the named `db-data` volume. **Adding `--volumes` deletes the database and all reservations.** Normal restarts and reseeding need no reset. For existing slugs the seed updates only the description; old dates, capacities and seat counts stay.

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

To diagnose counter drift, run this query in `psql`. It returns only inconsistent workshops, without emails:

```sql
SELECT w.id, w.reserved,
       count(r.id) FILTER (WHERE r.status = 'active') AS active_reservations
FROM workshops AS w
LEFT JOIN reservations AS r ON r.workshop_id = w.id
GROUP BY w.id, w.reserved
HAVING w.reserved <> count(r.id) FILTER (WHERE r.status = 'active');
```

Investigate how writes bypassed the reservation service before planning a repair.

## Deployment boundary

The Compose stack is a local demo. Before public deployment:

- Add emailed confirmation links or logins and rate limiting. Anyone knowing an email can reserve, cancel, or retrieve its existing reservation's name.
- Use HTTPS, managed secrets, and restricted database access.
- Define retention and deletion rules for names and emails, including cancelled reservations; avoid logging request bodies.
- Configure backups and test restoration. A persistent volume is not a backup.
- Monitor request failures, latency, database connections, and listener recovery. Health checks alone do not verify reservation or event delivery.
- Replace automatic demo seeding with a deliberate migration and reference-data process.

See the [scaling path](architecture.md#scaling-path) before adding workers or replicas.
