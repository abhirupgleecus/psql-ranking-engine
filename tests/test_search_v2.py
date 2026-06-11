import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_search_v2_endpoint_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/search/v2", params={"q": "HP Laptop", "top_n": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "HP Laptop"
    assert "search_mode" in data
    assert "results" in data
    assert len(data["results"]) > 0
    first_result = data["results"][0]
    assert "uuid" in first_result
    assert "search_score" in first_result
    assert "search_mode" in first_result


@pytest.mark.asyncio
async def test_search_v2_endpoint_category_prefilter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/search/v2",
            params={"q": "HP", "category": "Electronics", "top_n": 10}
        )
    assert response.status_code == 200
    data = response.json()
    for result in data["results"]:
        assert result["category"] == "Electronics"


@pytest.mark.asyncio
async def test_search_v2_endpoint_empty_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/search/v2", params={"q": "   "})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_v2_endpoint_fallback_disabled():
    # A query that will not match anything in FTS
    # (e.g. some gibberish that would trigger wildcard if enabled)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/search/v2",
            params={"q": "xyzrandomgibberish123", "fallback_enabled": False}
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 0
    assert data["search_mode"] == "fulltext"

