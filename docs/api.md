# API reference

[README](../README.md) · [Architecture](architecture.md) · [Contributing](../CONTRIBUTING.md) · [Operations](operations.md)

## Base URL and contracts

Use `http://localhost:8080/api` for the Compose stack or `http://localhost:8000/api` for the host development API. nginx and Vite forward `/api` unchanged.

FastAPI exposes Swagger UI at <http://localhost:8000/docs>, ReDoc at <http://localhost:8000/redoc>, and the generated schema at <http://localhost:8000/openapi.json>. These URLs are available in host development; nginx and Vite proxy only `/api`. Pydantic models in [`schemas.py`](../backend/app/schemas.py) define body shapes. This guide also records domain errors and dynamic statuses that are not all declared in the generated OpenAPI schema.

JSON request bodies require `Content-Type: application/json`. There is currently no authentication. Reservation responses omit emails, but an existing reservation's name is returned to anyone submitting its email.

| Method | Path                                      | Success                  | Other documented outcomes                                 |
| ------ | ----------------------------------------- | ------------------------ | --------------------------------------------------------- |
| GET    | `/api/health`                             | 200                      | —                                                         |
| GET    | `/api/workshops`                          | 200                      | —                                                         |
| POST   | `/api/workshops/{id}/reservations`        | 201 new; 200 existing    | 404 unknown; 409 full; 422 invalid; 503 cancellation race |
| POST   | `/api/workshops/{id}/reservations/cancel` | 200                      | 404 unknown; 422 invalid                                  |
| GET    | `/api/events`                             | 200, `text/event-stream` | Connection may end; reconnect and reload                  |

## List and health

`GET /api/health` returns `{"status":"ok"}`. It is an HTTP liveness check, not a database or event-delivery readiness check.

`GET /api/workshops` returns a JSON array ordered by `starts_at`, or `[]` when empty. An illustrative item is:

```json
{
  "id": 1,
  "title": "Intro to Pottery",
  "starts_at": "2026-10-19T10:00:00Z",
  "capacity": 8,
  "remaining": 8
}
```

IDs, dates, and remaining counts depend on your database. There is no pagination, reservation lookup endpoint, or workshop management endpoint.

## Reserve

`POST /api/workshops/{id}/reservations` accepts:

```json
{
  "name": "Ada Example",
  "email": "ada@example.com"
}
```

- `id` must be an integer from 1 through 2,147,483,647.
- `name` is trimmed, must contain 1–100 characters after trimming, and cannot contain NUL.
- `email` must pass Pydantic `EmailStr` validation. Surrounding whitespace is trimmed; active reservations are matched case-insensitively in PostgreSQL.

A new reservation returns 201. A retry with an email that already holds a seat returns 200 with the existing reservation ID and original name, even if another name was submitted. Both use this shape:

```json
{
  "id": 7,
  "workshop_id": 1,
  "name": "Ada Example",
  "remaining": 7
}
```

`remaining` is a snapshot, not a promise that no later changes occurred. The frontend uses SSE/list responses for displayed counts. To recover from an uncertain reserve response, submit the same workshop/email again. The duplicate protection lasts while the reservation is active; reserving after cancellation can create a new seat.

## Cancel

`POST /api/workshops/{id}/reservations/cancel` accepts `{"email":"ada@example.com"}` with the same ID and email validation rules.

For any known workshop, it returns 200 with exactly:

```json
{
  "message": "If this email held a seat, it has been cancelled."
}
```

The message is the same for a newly cancelled reservation, an already cancelled one, and an email that never held a seat. It does not confirm prior membership. A valid but unknown workshop ID returns 404.

## Errors

| HTTP status | JSON `detail`                                       | Meaning                                                             |
| ----------- | --------------------------------------------------- | ------------------------------------------------------------------- |
| 404         | `Workshop not found`                                | Valid ID with no workshop row                                       |
| 409         | `Workshop is full`                                  | No new seat was reserved; the transaction rolled back               |
| 503         | `Reservation changed while reserving; please retry` | Both reserve attempts raced with cancellation; retry the same input |
| 422         | Array of validation errors                          | Invalid path or request body; inspect `loc`, `msg`, and `type`      |

Domain errors have the shape `{"detail":"Workshop is full"}`. Validation-error fields are generated by FastAPI/Pydantic and may include additional context. A malformed ID produces 422 before workshop lookup, rather than 404.

## Try the API

Start the stack using the [README](../README.md#run-with-docker) first. For host development, change `API_URL` to `http://localhost:8000/api`. These commands create and then cancel a demo reservation. List workshops and set `WORKSHOP_ID` to an actual ID with a free seat; `1` is only an example. Use an email that is not already reserved if you want to observe 201 followed by 200.

```sh
API_URL=http://localhost:8080/api
curl --fail "$API_URL/workshops"
WORKSHOP_ID=1

curl -i -X POST "$API_URL/workshops/$WORKSHOP_ID/reservations" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada Example","email":"ada@example.com"}'

curl -i -X POST "$API_URL/workshops/$WORKSHOP_ID/reservations" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada Example","email":"ada@example.com"}'

curl -i -X POST "$API_URL/workshops/$WORKSHOP_ID/reservations/cancel" \
  -H 'Content-Type: application/json' \
  -d '{"email":"ada@example.com"}'
```

## SSE contract

Open this in a second terminal before reserving or cancelling:

```sh
curl -N http://localhost:8080/api/events # Use port 8000 for host development
```

A committed seat change produces a default SSE message with JSON data:

```text
data: {"workshop_id":1,"remaining":7}

```

JSON whitespace may vary. Keepalive comments arrive every 15 seconds; they are not seat changes. Repeated reserves, no-op cancellations, and rolled-back transactions do not emit seat-change messages.

The stream has no initial workshop snapshot, event IDs, or history replay. A client should load `/api/workshops` immediately and again whenever its stream opens or reconnects, then patch counts from events. Slow subscribers are disconnected rather than buffered indefinitely. Do not infer that a quiet stream means the workshop list is empty.
