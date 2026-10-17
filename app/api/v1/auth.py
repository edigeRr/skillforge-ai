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


# How to verify the registration feature
# ======================================
#
# 1. In the browser
#      docker compose up --build
#      docker compose exec api alembic upgrade head        (first run only)
#    Open http://localhost:8000/register, fill in the form and press "Create account".
#    Expected: you land on the home page, the nav shows Dashboard / Interview / Log out, and
#    both tokens are stored in the browser (DevTools > Application > Local Storage).
#    Open /register again and use the same email. Expected: "An account with that email
#    already exists" above the form, with the email field highlighted.
#
# 2. Straight against the API (macOS, Linux, Git Bash)
#      curl -i -X POST http://localhost:8000/api/v1/auth/register \
#        -H "Content-Type: application/json" \
#        -d '{"email": "demo@example.com", "password": "Str0ngPass1", "name": "Demo"}'
#    Expected: 201 and the new user (id, email, name, created_at) - no password in the response.
#    Repeat the command: 409 EMAIL_ALREADY_EXISTS. Send the password "OnlyLetters": 422.
#      curl -i -X POST http://localhost:8000/api/v1/auth/login \
#        -H "Content-Type: application/json" \
#        -d '{"email": "demo@example.com", "password": "Str0ngPass1"}'
#    Expected: 200 with access_token and refresh_token.
#
#    Windows PowerShell has no real curl (it is an alias for Invoke-WebRequest), so use:
#      Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/register `
#        -ContentType "application/json" `
#        -Body '{"email": "demo@example.com", "password": "Str0ngPass1", "name": "Demo"}'
#
#    Register and login share one limit of 5 requests per minute per IP. A 429 means: wait.
#
# 3. Automated tests (create the virtual environment first, as in README.md > Testing)
#    The backend tests drop and recreate the tables of the database in DATABASE_URL, so never
#    aim them at the dev database - they would erase the accounts you just created. Use a
#    separate database (the variable below lasts for the current terminal window only):
#      docker compose up -d db redis
#      docker compose exec db createdb -U skillforge skillforge_test
#      $env:DATABASE_URL="postgresql+asyncpg://skillforge:skillforge@localhost:5432/skillforge_test"
#      pytest tests/integration/test_auth_flow.py tests/integration/test_pages.py -q
#    On macOS / Linux put DATABASE_URL=... in front of the pytest command instead.
#    The frontend tests need Node.js 20 or newer:
#      cd tests-frontend
#      npm install
#      npm test


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
