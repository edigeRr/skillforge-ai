from pydantic import BaseModel

from app.models.user import Role
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserResponse


class CreateUserRequest(RegisterRequest):
    role: Role = Role.USER


class UpdateRoleRequest(BaseModel):
    role: Role


class PaginatedUsers(BaseModel):
    items: list[UserResponse]
    page: int
    page_size: int
    total: int
