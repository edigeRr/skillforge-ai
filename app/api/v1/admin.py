from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_user_repository, require_admin
from app.core.rate_limit import general_write_rate_limit
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.admin import CreateUserRequest, PaginatedUsers, UpdateRoleRequest
from app.schemas.user import UserResponse
from app.services.admin_service import AdminService

router = APIRouter(dependencies=[Depends(require_admin)])


def get_admin_service(users: UserRepository = Depends(get_user_repository)) -> AdminService:
    return AdminService(users)


# How to verify the admin feature
# ===============================
#
# 1. Make the first admin (the API can't, since nobody is an admin yet)
#      docker compose up --build
#      docker compose exec api alembic upgrade head
#    Register an account at http://localhost:8000/register, then promote it:
#      docker compose exec api python scripts/make_admin.py demo@example.com
#    Expected: "demo@example.com is now an admin." An unknown email exits with an error.
#    Log in again (or open /docs and Authorize) to use a token for that account.
#
# 2. Straight against the API (macOS, Linux, Git Bash; TOKEN is the admin's access token)
#      curl -H "Authorization: Bearer $TOKEN" \
#        "http://localhost:8000/api/v1/admin/users?page=1&page_size=20"
#    Expected: 200 with items (newest first, each with its role), page, page_size and total.
#      curl -i -X POST http://localhost:8000/api/v1/admin/users \
#        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
#        -d '{"email": "new@example.com", "password": "Str0ngPass1", "name": "New", "role": "user"}'
#    Expected: 201 with the new account. The same email again: 409 EMAIL_ALREADY_EXISTS.
#      curl -i -X PATCH http://localhost:8000/api/v1/admin/users/<id>/role \
#        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
#        -d '{"role": "admin"}'
#    Expected: 200 with role "admin". Your own id: 409 CANNOT_CHANGE_OWN_ROLE. An unknown id:
#    404 USER_NOT_FOUND. role "owner": 422. Any of these with a non-admin token: 403
#    ADMIN_REQUIRED; with no token: 401.
#
#    Windows PowerShell:
#      Invoke-RestMethod -Uri "http://localhost:8000/api/v1/admin/users" `
#        -Headers @{ Authorization = "Bearer $TOKEN" }
#
# 3. Automated tests (same test database as in step 3 of the registration block in auth.py)
#      pytest tests/integration/test_admin_flow.py tests/unit/test_admin_service.py -q


@router.get("/users", response_model=PaginatedUsers, summary="List accounts (admin)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    users: UserRepository = Depends(get_user_repository),
) -> PaginatedUsers:
    """All accounts, newest first. Admins only (`403 ADMIN_REQUIRED` otherwise)."""
    items, total = await users.list_page(page=page, page_size=page_size)
    return PaginatedUsers(
        items=[UserResponse.model_validate(u) for u in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Create an account (admin)",
)
async def create_user(
    payload: CreateUserRequest, admin: AdminService = Depends(get_admin_service)
) -> User:
    """Create an account with any role. Same password rules as registration;
    `409 EMAIL_ALREADY_EXISTS` if the email is taken."""
    return await admin.create_user(payload.email, payload.password, payload.name, payload.role)


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Change an account's role (admin)",
)
async def change_role(
    user_id: UUID,
    payload: UpdateRoleRequest,
    current_admin: User = Depends(require_admin),
    admin: AdminService = Depends(get_admin_service),
) -> User:
    """Set another account's role. `409 CANNOT_CHANGE_OWN_ROLE` for your own
    account, so the last admin can't lock everyone out; `404 USER_NOT_FOUND`
    for an unknown id."""
    return await admin.change_role(current_admin, user_id, payload.role)
