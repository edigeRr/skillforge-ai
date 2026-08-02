from fastapi import APIRouter, Depends, status

from app.api.deps import get_refresh_token_repository, get_user_repository
from app.core.rate_limit import auth_rate_limit, general_write_rate_limit
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


def get_auth_service(
    users: UserRepository = Depends(get_user_repository),
    refresh_tokens: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> AuthService:
    return AuthService(users, refresh_tokens)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
    summary="Create an account",
)
async def register(payload: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> User:
    """Register a new user. Password must be 8-72 characters with at least
    one letter and one digit. Returns `409 EMAIL_ALREADY_EXISTS` if the
    email is already registered."""
    return await auth.register(payload.email, payload.password, payload.name)


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limit)],
    summary="Log in",
)
async def login(
    payload: LoginRequest, auth: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Exchange email + password for an access token (short-lived) and a
    refresh token (long-lived). Copy the `access_token` into the
    **Authorize** button above (as `Bearer <token>`) to call protected
    endpoints from this page."""
    result = await auth.login(payload.email, payload.password)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Rotate an access token",
)
async def refresh(
    payload: RefreshRequest, auth: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Exchange a refresh token for a new access token. The refresh token
    itself is single-use and rotates on every call - the old one is
    revoked, so reusing it returns `401 INVALID_REFRESH_TOKEN`."""
    result = await auth.refresh(payload.refresh_token)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Log out",
)
async def logout(payload: RefreshRequest, auth: AuthService = Depends(get_auth_service)) -> None:
    """Revoke a refresh token server-side, so it can no longer be used to
    get new access tokens even if it leaks."""
    await auth.logout(payload.refresh_token)
