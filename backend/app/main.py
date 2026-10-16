"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.db import engine
from app.routes import router as workshops_router

api = APIRouter(prefix="/api")
api.include_router(workshops_router)


@api.get("/health")
async def health() -> dict[str, str]:
    """Report that the API is up."""
    return {"status": "ok"}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Close the database connection pool when the app shuts down."""
    yield
    await engine.dispose()


app = FastAPI(title="Workshop Reservations", lifespan=lifespan)
app.include_router(api)
