"""Search works through nginx, on the models baked into the API image.

Needs the stack up (`docker compose up -d --wait`); run with `uv run pytest smoke`.
"""

import httpx
import pytest

WEB_URL = "http://localhost:8080"


@pytest.mark.parametrize("mode", ["semantic", "rerank"])
async def test_model_search_returns_listed_workshops_through_nginx(mode: str) -> None:
    """The startup index serves the model-backed modes; every id is listed."""
    async with httpx.AsyncClient(base_url=WEB_URL) as client:
        workshops = (await client.get("/api/workshops")).json()
        response = await client.get(
            "/api/workshops/search", params={"q": "bread", "mode": mode}
        )

    assert response.status_code == 200
    found_ids = response.json()
    assert found_ids
    listed_ids = {workshop["id"] for workshop in workshops}
    assert set(found_ids) <= listed_ids
