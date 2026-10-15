"""Tests for the health endpoint."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_reports_ok() -> None:
    """GET /api/health answers 200 with status ok."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
