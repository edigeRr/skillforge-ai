import json
from dataclasses import asdict, dataclass
from uuid import UUID

from app.core.cache_keys import dashboard_stats_key
from app.db.redis import redis_client
from app.repositories.interview_repository import InterviewRepository
from app.repositories.question_repository import QuestionRepository

MIN_TOPIC_DATA_POINTS = 2
TOP_TOPICS_COUNT = 3
CACHE_TTL_SECONDS = 5 * 60


@dataclass
class TopicStat:
    topic: str
    average_score: float


@dataclass
class DashboardStats:
    total_interviews: int
    average_score: float | None
    best_topics: list[TopicStat]
    weak_topics: list[TopicStat]


class DashboardService:
    def __init__(self, interviews: InterviewRepository, questions: QuestionRepository) -> None:
        self.interviews = interviews
        self.questions = questions

    async def get_stats(self, user_id: UUID) -> DashboardStats:
        cache_key = dashboard_stats_key(user_id)
        cached = await redis_client.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            return DashboardStats(
                total_interviews=data["total_interviews"],
                average_score=data["average_score"],
                best_topics=[TopicStat(**t) for t in data["best_topics"]],
                weak_topics=[TopicStat(**t) for t in data["weak_topics"]],
            )

        stats = await self._compute_stats(user_id)
        await redis_client.set(cache_key, json.dumps(asdict(stats)), ex=CACHE_TTL_SECONDS)
        return stats

    async def _compute_stats(self, user_id: UUID) -> DashboardStats:
        total, average_score = await self.interviews.stats_for_user(user_id)
        topic_stats = await self.questions.topic_stats_for_user(
            user_id, min_data_points=MIN_TOPIC_DATA_POINTS
        )

        best = [
            TopicStat(topic=t, average_score=round(s, 2))
            for t, s in sorted(topic_stats, key=lambda item: item[1], reverse=True)[
                :TOP_TOPICS_COUNT
            ]
        ]
        weak = [
            TopicStat(topic=t, average_score=round(s, 2))
            for t, s in sorted(topic_stats, key=lambda item: item[1])[:TOP_TOPICS_COUNT]
        ]

        return DashboardStats(
            total_interviews=total,
            average_score=round(average_score, 2) if average_score is not None else None,
            best_topics=best,
            weak_topics=weak,
        )
