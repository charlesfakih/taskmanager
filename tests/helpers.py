from typing import Any

from httpx import AsyncClient


def auth_headers(user_id: int) -> dict:
    return {"X-User-Id": str(user_id)}


async def gql(
    client: AsyncClient,
    query: str,
    variables: dict | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    headers = auth_headers(user_id) if user_id is not None else {}
    response = await client.post(
        "/graphql", json={"query": query, "variables": variables or {}}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()
