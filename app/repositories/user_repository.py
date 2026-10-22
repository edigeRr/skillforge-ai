from sqlalchemy import func, select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_page(self, *, page: int, page_size: int) -> tuple[list[User], int]:
        total = (await self.session.execute(select(func.count()).select_from(User))).scalar_one()
        result = await self.session.execute(
            select(User)
            .order_by(User.created_at.desc(), User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
