from uuid import UUID

from sqlalchemy import func, select

from app.models.question import Question
from app.repositories.base import BaseRepository


class QuestionRepository(BaseRepository[Question]):
    model = Question

    async def list_by_interview(self, interview_id: UUID) -> list[Question]:
        result = await self.session.execute(
            select(Question)
            .where(Question.interview_id == interview_id)
            .order_by(Question.order_index)
        )
        return list(result.scalars().all())

    async def count_by_interview(self, interview_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Question).where(Question.interview_id == interview_id)
        )
        return result.scalar_one()

    async def list_topics_by_interview(self, interview_id: UUID) -> list[str]:
        result = await self.session.execute(
            select(Question.topic).where(Question.interview_id == interview_id)
        )
        return list(result.scalars().all())

    async def list_answered_by_interview(self, interview_id: UUID) -> list[Question]:
        result = await self.session.execute(
            select(Question).where(
                Question.interview_id == interview_id, Question.answer.is_not(None)
            )
        )
        return list(result.scalars().all())
