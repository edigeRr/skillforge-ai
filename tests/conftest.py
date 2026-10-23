import asyncio
import os

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import URL, make_url

from app.core.config import Settings


async def _create_database_if_missing(url: URL) -> None:
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database="postgres",
        timeout=5,
    )
    try:
        if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", url.database):
            await conn.execute(f'CREATE DATABASE "{url.database}"')
    finally:
        await conn.close()


def _use_test_database() -> None:
    """The fixtures below drop every table, so they must never run against a
    real database. Point DATABASE_URL at <name>_test on the same server (unless
    the name already ends in _test, as in CI) and create it if it's missing.
    Runs before app.db.session builds its engine. Without a reachable server it
    creates nothing and the tests fail on their first database call as before."""
    url = make_url(Settings().DATABASE_URL)
    if not url.database.endswith("_test"):
        url = url.set(database=f"{url.database}_test")
        os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    try:
        asyncio.run(_create_database_if_missing(url))
    except (OSError, asyncpg.PostgresError):
        pass


_use_test_database()

import app.models  # noqa: E402,F401 - registers models on Base.metadata
from app.db.redis import redis_client  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _clean_state():
    """Reset tables and flush Redis before every test for isolation
    (both between DB rows and rate-limiter counters)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await redis_client.flushdb()
    yield


async def register_and_login(
    client: AsyncClient, email: str, password: str = "Str0ngPass1"
) -> dict[str, str]:
    """Shared by any test file that needs an authenticated user without
    caring about the auth flow itself."""
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "name": "Test User"}
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
