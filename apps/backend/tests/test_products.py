import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_products_empty(client: AsyncClient):
    response = await client.get("/products/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0
