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


@pytest.mark.asyncio
async def test_search_v2_model_number_substring():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Search for a mid-string substring of the model number "15-eg0050wm" (e.g. "eg0050")
        response = await ac.get("/search/v2", params={"q": "eg0050", "top_n": 3})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    assert data["results"][0]["uuid"] == "31599cae-55c1-463a-b256-80f1b5fcd041"


@pytest.mark.asyncio
async def test_search_v2_model_number_substring_laserjet():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Search for "4201dw" (model number for "b9ca619c-1828-4593-900c-582d17720457")
        # Let's search a substring like "4201d"
        response = await ac.get("/search/v2", params={"q": "4201d", "top_n": 3})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    assert data["results"][0]["uuid"] == "b9ca619c-1828-4593-900c-582d17720457"


@pytest.mark.asyncio
async def test_search_v2_upc_exact():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Search for exact UPC "14817624144" (Monte Carlo Roulis 52-inch LED Ceiling Fan)
        response = await ac.get("/search/v2", params={"q": "14817624144", "top_n": 3})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    assert data["results"][0]["uuid"] == "6e8f8e4f-f515-40f7-adf7-bad981bb1e98"


@pytest.mark.asyncio
async def test_search_v2_upc_substring():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Search for partial UPC "24458" (Monte Carlo Rozzen 44-inch Ceiling Fan, UPC 014817624458 / 14817624458)
        response = await ac.get("/search/v2", params={"q": "24458", "top_n": 3})
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    assert data["results"][0]["uuid"] in [
        "bd349a7f-93fc-4164-b470-df250e3b4611",
        "07df4deb-130b-465a-81e7-727bac5bb32c"
    ]




