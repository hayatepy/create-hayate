import pytest

from app import app
from tests.helpers import AUTH_HEADERS


@pytest.mark.asyncio
async def test_openapi_and_scalar_come_from_the_registered_routes():
    response = await app.request("/openapi.json", headers=AUTH_HEADERS)
    assert response.status == 200
    document = await response.json()
    assert document["openapi"] == "3.1.1"
    assert "/todos" in document["paths"]
    assert document["paths"]["/todos"]["post"]["operationId"] == "createTodo"

    docs = await app.request("/docs", headers=AUTH_HEADERS)
    assert docs.status == 200
    assert "content-security-policy" in docs.headers
