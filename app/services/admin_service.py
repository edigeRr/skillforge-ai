from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import Role, User
from app.repositories.user_repository import UserRepository


class AdminService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    async def create_user(self, email: str, password: str, name: str, role: Role) -> User:
        if await self.users.get_by_email(email) is not None:
            raise ConflictError(
                "A user with this email already exists.", error_code="EMAIL_ALREADY_EXISTS"
            )
        user = User(email=email, password_hash=hash_password(password), name=name, role=role)
        return await self.users.add(user)

    async def change_role(self, admin: User, user_id: UUID, role: Role) -> User:
        if user_id == admin.id:
            raise ConflictError(
                "Administrators cannot change their own role.",
                error_code="CANNOT_CHANGE_OWN_ROLE",
            )
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.", error_code="USER_NOT_FOUND")
        user.role = role
        return await self.users.add(user)
