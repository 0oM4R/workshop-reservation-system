"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI

api = APIRouter(prefix="/api")


@api.get("/health")
async def health() -> dict[str, str]:
    """Report that the API is up."""
    return {"status": "ok"}


app = FastAPI(title="Workshop Reservations")
app.include_router(api)
