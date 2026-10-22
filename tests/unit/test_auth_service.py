from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import Role, User
from app.services.auth_service import AuthService


def make_service():
    users = AsyncMock()
    refresh_tokens = AsyncMock()
    return AuthService(users, refresh_tokens), users, refresh_tokens


async def test_register_creates_user_when_email_is_free():
    service, users, _ = make_service()
    users.get_by_email.return_value = None
    users.add.side_effect = lambda u: u

    user = await service.register("new@example.com", "Password1", "New User")

    assert user.email == "new@example.com"
    users.add.assert_awaited_once()


async def test_register_rejects_duplicate_email():
    service, users, _ = make_service()
    users.get_by_email.return_value = User(email="taken@example.com", password_hash="x", name="X")

    with pytest.raises(ConflictError):
        await service.register("taken@example.com", "Password1", "New User")


async def test_login_rejects_wrong_password():
    service, users, _ = make_service()
    users.get_by_email.return_value = User(
        email="user@example.com", password_hash=hash_password("correct-pass1"), name="User"
    )

    with pytest.raises(UnauthorizedError):
        await service.login("user@example.com", "wrong-pass1")


async def test_login_issues_tokens_on_success():
    service, users, refresh_tokens = make_service()
    user = User(
        id=uuid4(),
        email="user@example.com",
        password_hash=hash_password("correct-pass1"),
        name="User",
    )
    users.get_by_email.return_value = user
    refresh_tokens.add.side_effect = lambda rt: rt

    result = await service.login("user@example.com", "correct-pass1")

    assert result.access_token
    assert result.refresh_token
    refresh_tokens.add.assert_awaited_once()


async def test_refresh_rejects_revoked_token():
    service, _, refresh_tokens = make_service()
    stored = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="irrelevant",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked=True,
    )
    refresh_tokens.get_by_hash.return_value = stored

    with pytest.raises(UnauthorizedError):
        await service.refresh("some-raw-token")


async def test_refresh_rejects_expired_token():
    service, _, refresh_tokens = make_service()
    stored = RefreshToken(
        id=uuid4(),
        user_id=uuid4(),
        token_hash="irrelevant",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        revoked=False,
    )
    refresh_tokens.get_by_hash.return_value = stored

    with pytest.raises(UnauthorizedError):
        await service.refresh("some-raw-token")


def access_claims(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def valid_refresh_token(user_id) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        user_id=user_id,
        token_hash="irrelevant",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        revoked=False,
    )


async def test_refresh_rotates_token_on_success():
    service, users, refresh_tokens = make_service()
    user = User(id=uuid4(), email="user@example.com", password_hash="x", name="User", role="user")
    stored = valid_refresh_token(user.id)
    users.get_by_id.return_value = user
    refresh_tokens.get_by_hash.return_value = stored
    refresh_tokens.add.side_effect = lambda rt: rt

    result = await service.refresh("some-raw-token")

    refresh_tokens.revoke.assert_awaited_once_with(stored.id)
    assert result.access_token
    assert result.refresh_token != "some-raw-token"


async def test_login_puts_the_role_in_the_access_token():
    service, users, refresh_tokens = make_service()
    users.get_by_email.return_value = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash=hash_password("correct-pass1"),
        name="Admin",
        role=Role.ADMIN,
    )
    refresh_tokens.add.side_effect = lambda rt: rt

    result = await service.login("admin@example.com", "correct-pass1")

    assert access_claims(result.access_token)["role"] == "admin"


async def test_refresh_uses_the_role_the_account_has_now():
    service, users, refresh_tokens = make_service()
    user = User(id=uuid4(), email="u@example.com", password_hash="x", name="U", role=Role.ADMIN)
    users.get_by_id.return_value = user
    refresh_tokens.get_by_hash.return_value = valid_refresh_token(user.id)
    refresh_tokens.add.side_effect = lambda rt: rt

    result = await service.refresh("some-raw-token")

    assert access_claims(result.access_token)["role"] == "admin"


async def test_refresh_rejects_a_token_whose_account_is_gone():
    service, users, refresh_tokens = make_service()
    users.get_by_id.return_value = None
    refresh_tokens.get_by_hash.return_value = valid_refresh_token(uuid4())

    with pytest.raises(UnauthorizedError):
        await service.refresh("some-raw-token")

    refresh_tokens.revoke.assert_not_awaited()
