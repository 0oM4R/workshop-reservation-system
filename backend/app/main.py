"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.db import engine
from app.routes import router as workshops_router
from app.services.reservations import WorkshopFull, WorkshopNotFound

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


@app.exception_handler(WorkshopNotFound)
async def workshop_not_found(
    _request: Request, _error: WorkshopNotFound
) -> JSONResponse:
    """Map an unknown workshop to 404."""
    return JSONResponse(
        {"detail": "Workshop not found"}, status_code=status.HTTP_404_NOT_FOUND
    )


@app.exception_handler(WorkshopFull)
async def workshop_full(_: Request, __: WorkshopFull) -> JSONResponse:
    """Map a full workshop to 409."""
    return JSONResponse(
        {"detail": "Workshop is full"}, status_code=status.HTTP_409_CONFLICT
    )
