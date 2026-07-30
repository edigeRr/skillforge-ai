import pytest
from httpx import ASGITransport, AsyncClient

import app.models  # noqa: F401 - registers models on Base.metadata
from app.db.redis import redis_client
from app.db.session import Base, engine
from app.main import app


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
