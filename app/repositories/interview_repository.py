from uuid import UUID

from sqlalchemy import func, select

from app.models.interview import Interview
from app.repositories.base import BaseRepository


class InterviewRepository(BaseRepository[Interview]):
    model = Interview

    async def get_active_for_user(self, user_id: UUID) -> Interview | None:
        result = await self.session.execute(
            select(Interview).where(Interview.user_id == user_id, Interview.status == "in_progress")
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        *,
        page: int,
        page_size: int,
        language: str | None = None,
        difficulty: str | None = None,
        status: str | None = None,
    ) -> tuple[list[Interview], int]:
        filters = [Interview.user_id == user_id]
        if language:
            filters.append(Interview.language == language)
        if difficulty:
            filters.append(Interview.difficulty == difficulty)
        if status:
            filters.append(Interview.status == status)

        count_result = await self.session.execute(
            select(func.count()).select_from(Interview).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Interview)
            .where(*filters)
            .order_by(Interview.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def stats_for_user(self, user_id: UUID) -> tuple[int, float | None]:
        """Returns (total completed interviews, average score) for the user."""
        result = await self.session.execute(
            select(func.count(Interview.id), func.avg(Interview.score)).where(
                Interview.user_id == user_id, Interview.status == "completed"
            )
        )
        total, avg_score = result.one()
        return total, float(avg_score) if avg_score is not None else None
