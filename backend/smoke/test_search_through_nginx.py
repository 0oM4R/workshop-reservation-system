"""Search works through nginx, on the model baked into the API image.

Needs the stack up (`docker compose up -d --wait`); run with `uv run pytest smoke`.
"""

import httpx

WEB_URL = "http://localhost:8080"


async def test_semantic_search_returns_listed_workshops_through_nginx() -> None:
    """The startup index serves semantic search, and every id is a listed workshop."""
    async with httpx.AsyncClient(base_url=WEB_URL) as client:
        workshops = (await client.get("/api/workshops")).json()
        response = await client.get(
            "/api/workshops/search", params={"q": "bread", "mode": "semantic"}
        )

    assert response.status_code == 200
    found_ids = response.json()
    assert found_ids
    listed_ids = {workshop["id"] for workshop in workshops}
    assert set(found_ids) <= listed_ids
