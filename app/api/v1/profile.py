from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_repository
from app.core.rate_limit import general_write_rate_limit
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UpdateProfileRequest, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse, summary="View your profile")
async def get_my_profile(current_user: User = Depends(get_current_user)) -> User:
    """Returns the currently authenticated user's profile."""
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Update your display name",
)
async def update_my_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
) -> User:
    """Update the display name on the current user's profile. Email isn't
    editable here (that would need a re-verification flow, out of scope
    for v1 - see requirements.md)."""
    current_user.name = payload.name
    return await users.add(current_user)
