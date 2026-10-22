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
    "/admin",
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


async def test_browsers_get_the_404_page_for_unknown_addresses(client):
    response = await client.get("/no-such-page", headers={"accept": "text/html"})

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "Page not found" in response.text
    for asset in ASSET_REFERENCE.findall(response.text):
        assert (await client.get(asset)).status_code == 200


@pytest.mark.parametrize(
    ("path", "accept"),
    [
        ("/no-such-page", "application/json"),
        ("/api/v1/no-such-endpoint", "text/html"),
        ("/static/no-such-file.css", "text/html"),
    ],
)
async def test_api_clients_and_static_files_keep_the_json_404(client, path, accept):
    response = await client.get(path, headers={"accept": accept})

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


@pytest.mark.parametrize("path", ["/admin", "/static/js/api.js", "/static/css/style.css"])
async def test_pages_and_assets_must_be_revalidated(client, path):
    response = await client.get(path)

    assert response.headers["cache-control"] == "no-cache"


async def test_the_404_page_must_be_revalidated(client):
    response = await client.get("/no-such-page", headers={"accept": "text/html"})

    assert response.headers["cache-control"] == "no-cache"


async def test_an_unchanged_asset_is_answered_with_304(client):
    first = await client.get("/static/js/api.js")

    second = await client.get("/static/js/api.js", headers={"if-none-match": first.headers["etag"]})

    assert second.status_code == 304
