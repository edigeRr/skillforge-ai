from sqlalchemy import update

from app.db.session import async_session_factory
from app.models.user import Role, User
from tests.conftest import register_and_login


async def make_admin(client, email: str) -> dict[str, str]:
    headers = await register_and_login(client, email)
    async with async_session_factory() as session:
        await session.execute(update(User).where(User.email == email).values(role=Role.ADMIN))
        await session.commit()
    return headers


async def test_new_accounts_get_the_user_role(client):
    headers = await register_and_login(client, "plain@example.com")

    me = await client.get("/api/v1/profile/me", headers=headers)

    assert me.json()["role"] == "user"


async def test_admin_routes_reject_missing_and_non_admin_tokens(client):
    headers = await register_and_login(client, "plain@example.com")

    no_token = await client.get("/api/v1/admin/users")
    not_admin = await client.get("/api/v1/admin/users", headers=headers)

    assert no_token.status_code == 401
    assert not_admin.status_code == 403
    assert not_admin.json()["error_code"] == "ADMIN_REQUIRED"


async def test_admin_creates_accounts_and_lists_them(client):
    headers = await make_admin(client, "admin@example.com")
    payload = {"email": "new@example.com", "password": "Str0ngPass1", "name": "New"}

    created = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    duplicate = await client.post("/api/v1/admin/users", json=payload, headers=headers)
    listed = await client.get("/api/v1/admin/users?page=1&page_size=1", headers=headers)

    assert created.status_code == 201
    assert created.json()["role"] == "user"
    assert duplicate.status_code == 409
    assert listed.json()["total"] == 2
    assert [u["email"] for u in listed.json()["items"]] == ["new@example.com"]
    login = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "Str0ngPass1"}
    )
    assert login.status_code == 200


async def test_admin_changes_roles_but_not_their_own(client):
    headers = await make_admin(client, "admin@example.com")
    other = await client.post(
        "/api/v1/admin/users",
        json={"email": "other@example.com", "password": "Str0ngPass1", "name": "Other"},
        headers=headers,
    )
    me = await client.get("/api/v1/profile/me", headers=headers)

    promoted = await client.patch(
        f"/api/v1/admin/users/{other.json()['id']}/role", json={"role": "admin"}, headers=headers
    )
    own = await client.patch(
        f"/api/v1/admin/users/{me.json()['id']}/role", json={"role": "user"}, headers=headers
    )
    unknown = await client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/role",
        json={"role": "admin"},
        headers=headers,
    )
    bad_role = await client.patch(
        f"/api/v1/admin/users/{other.json()['id']}/role", json={"role": "owner"}, headers=headers
    )

    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"
    assert own.status_code == 409
    assert own.json()["error_code"] == "CANNOT_CHANGE_OWN_ROLE"
    assert unknown.status_code == 404
    assert bad_role.status_code == 422
