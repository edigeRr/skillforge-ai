async def test_health_reports_status(client):
    response = await client.get("/health")

    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["db"] in ("ok", "unavailable")
    assert body["redis"] in ("ok", "unavailable")
