from uuid import UUID

from sqlalchemy import func, select

from app.models.interview import Interview
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

    async def topic_stats_for_user(
        self, user_id: UUID, *, min_data_points: int = 2
    ) -> list[tuple[str, float]]:
        """(topic, average_score) across all the user's answered questions,
        for topics with at least `min_data_points` scored questions (FR-5.1 -
        one bad answer shouldn't be enough to brand a whole topic "weak")."""
        result = await self.session.execute(
            select(Question.topic, func.avg(Question.score))
            .join(Interview, Interview.id == Question.interview_id)
            .where(Interview.user_id == user_id, Question.score.is_not(None))
            .group_by(Question.topic)
            .having(func.count(Question.id) >= min_data_points)
        )
        return [(topic, float(avg_score)) for topic, avg_score in result.all()]
