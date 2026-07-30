from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_user_repository
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UpdateProfileRequest, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
) -> User:
    current_user.name = payload.name
    return await users.add(current_user)
