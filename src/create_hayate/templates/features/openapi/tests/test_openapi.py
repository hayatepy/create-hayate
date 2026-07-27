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
    create = document["paths"]["/todos"]["post"]
    assert create["operationId"] == "createTodo"
    create_schema = create["requestBody"]["content"]["application/json"]["schema"]
    assert create_schema["properties"]["title"]["minLength"] == 1
    assert create_schema["properties"]["title"]["maxLength"] == 200
    create_response = create["responses"]["201"]["content"]["application/json"]["schema"]
    assert create_response["properties"]["id"] == {
        "type": "string",
        "format": "uuid",
    }
    path_parameter = document["paths"]["/todos/{id}"]["get"]["parameters"][0]
    assert path_parameter == {
        "name": "id",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "format": "uuid"},
    }
    generated_response = document["paths"]["/todos/{id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert generated_response["properties"]["id"]["format"] == "uuid"

    docs = await app.request("/docs", headers=AUTH_HEADERS)
    assert docs.status == 200
    assert "content-security-policy" in docs.headers
