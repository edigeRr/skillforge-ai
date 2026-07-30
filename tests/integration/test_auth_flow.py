async def test_full_auth_lifecycle(client):
    register_payload = {"email": "jane@example.com", "password": "Str0ngPass", "name": "Jane"}
    register_resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert register_resp.status_code == 201
    assert register_resp.json()["email"] == "jane@example.com"

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "jane@example.com", "password": "Str0ngPass"}
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    me_resp = await client.get(
        "/api/v1/profile/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["name"] == "Jane"

    update_resp = await client.put(
        "/api/v1/profile/me",
        json={"name": "Jane Updated"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Jane Updated"

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert new_tokens["refresh_token"] != refresh_token

    # Old refresh token was rotated out - reusing it must fail.
    reuse_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse_resp.status_code == 401
    assert reuse_resp.json()["error_code"] == "INVALID_REFRESH_TOKEN"

    logout_resp = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert logout_resp.status_code == 204

    # Refresh token was revoked on logout - it must no longer work either.
    logout_reuse_resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert logout_reuse_resp.status_code == 401


async def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "Str0ngPass1", "name": "Dup"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


async def test_register_rejects_weak_password(client):
    payload = {"email": "weak@example.com", "password": "alllettersnodigits", "name": "Weak"}
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


async def test_login_rejects_wrong_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wp@example.com", "password": "Str0ngPass1", "name": "WP"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "wp@example.com", "password": "wrong-password-1"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


async def test_protected_route_rejects_missing_token(client):
    resp = await client.get("/api/v1/profile/me")
    assert resp.status_code == 401


async def test_protected_route_rejects_garbage_token(client):
    resp = await client.get(
        "/api/v1/profile/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "INVALID_TOKEN"
