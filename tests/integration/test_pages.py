import re

import pytest

PAGES = [
    "/",
    "/register",
    "/login",
    "/interview",
    "/interview/3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b",
    "/history",
    "/dashboard",
]
ASSET_REFERENCE = re.compile(r'(?:href|src)="(/static/[^"]+)"')


@pytest.mark.parametrize("path", PAGES)
async def test_page_is_served_as_html(client, path):
    response = await client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>" in response.text


@pytest.mark.parametrize("path", PAGES)
async def test_every_asset_a_page_references_is_served(client, path):
    html = (await client.get(path)).text
    assets = ASSET_REFERENCE.findall(html)

    assert assets
    for asset in assets:
        response = await client.get(asset)
        assert response.status_code == 200, f"{path} references {asset}, which is not served"


async def test_pages_are_not_part_of_the_openapi_schema(client):
    schema = (await client.get("/openapi.json")).json()

    for path in PAGES:
        assert path not in schema["paths"]


async def test_session_page_needs_an_interview_id_shaped_like_a_uuid(client):
    response = await client.get("/interview/not-an-id")

    assert response.status_code == 422
