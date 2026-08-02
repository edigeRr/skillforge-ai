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
)
async def register(payload: RegisterRequest, auth: AuthService = Depends(get_auth_service)) -> User:
    return await auth.register(payload.email, payload.password, payload.name)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(
    payload: LoginRequest, auth: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    result = await auth.login(payload.email, payload.password)
    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post(
    "/refresh", response_model=TokenResponse, dependencies=[Depends(general_write_rate_limit)]
)
async def refresh(
    payload: RefreshRequest, auth: AuthService = Depends(get_auth_service)
) -> TokenResponse:
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
)
async def logout(payload: RefreshRequest, auth: AuthService = Depends(get_auth_service)) -> None:
    await auth.logout(payload.refresh_token)
