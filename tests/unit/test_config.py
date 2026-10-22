import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://user:pass@host:5432/db",
        "postgres://user:pass@host:5432/db",
        "postgresql+asyncpg://user:pass@host:5432/db",
    ],
)
def test_database_url_uses_asyncpg(given):
    settings = Settings(DATABASE_URL=given)

    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/db"


def test_database_url_keeps_other_drivers():
    settings = Settings(DATABASE_URL="sqlite+aiosqlite:///./test.db")

    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./test.db"
