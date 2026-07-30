from dataclasses import dataclass
from uuid import UUID

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

settings = get_settings()


@dataclass
class AuthResult:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0


class AuthService:
    def __init__(self, users: UserRepository, refresh_tokens: RefreshTokenRepository) -> None:
        self.users = users
        self.refresh_tokens = refresh_tokens

    async def register(self, email: str, password: str, name: str) -> User:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise ConflictError(
                "A user with this email already exists.", error_code="EMAIL_ALREADY_EXISTS"
            )

        user = User(email=email, password_hash=hash_password(password), name=name)
        return await self.users.add(user)

    async def login(self, email: str, password: str) -> AuthResult:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.", error_code="INVALID_CREDENTIALS")
        return await self._issue_tokens(user.id)

    async def refresh(self, raw_refresh_token: str) -> AuthResult:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored = await self.refresh_tokens.get_by_hash(token_hash)

        if stored is None or stored.revoked or stored.is_expired:
            raise UnauthorizedError(
                "Refresh token is invalid or expired.", error_code="INVALID_REFRESH_TOKEN"
            )

        await self.refresh_tokens.revoke(stored.id)
        return await self._issue_tokens(stored.user_id)

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored = await self.refresh_tokens.get_by_hash(token_hash)
        if stored is not None:
            await self.refresh_tokens.revoke(stored.id)

    async def _issue_tokens(self, user_id: UUID) -> AuthResult:
        access_token = create_access_token(user_id)
        raw_refresh, token_hash, expires_at = generate_refresh_token()
        await self.refresh_tokens.add(
            RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        )
        return AuthResult(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
