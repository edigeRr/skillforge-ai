from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.cache_keys import dashboard_stats_key
from app.db.redis import redis_client
from app.services.dashboard_service import DashboardService


def make_service():
    interviews = AsyncMock()
    questions = AsyncMock()
    return DashboardService(interviews, questions), interviews, questions


async def test_get_stats_computes_and_caches_on_first_call():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interviews.stats_for_user.return_value = (5, 7.234)
    questions.topic_stats_for_user.return_value = [
        ("arrays", 9.0),
        ("concurrency", 3.0),
        ("recursion", 6.0),
        ("sql", 8.0),
    ]

    stats = await service.get_stats(user_id)

    assert stats.total_interviews == 5
    assert stats.average_score == 7.23
    assert [t.topic for t in stats.best_topics] == ["arrays", "sql", "recursion"]
    assert [t.topic for t in stats.weak_topics] == ["concurrency", "recursion", "sql"]

    cached_raw = await redis_client.get(dashboard_stats_key(user_id))
    assert cached_raw is not None


async def test_get_stats_uses_cache_on_second_call_without_recomputing():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interviews.stats_for_user.return_value = (5, 7.2)
    questions.topic_stats_for_user.return_value = [("arrays", 9.0), ("concurrency", 3.0)]

    first = await service.get_stats(user_id)
    second = await service.get_stats(user_id)

    assert first == second
    interviews.stats_for_user.assert_awaited_once()
    questions.topic_stats_for_user.assert_awaited_once()


async def test_get_stats_handles_no_completed_interviews():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interviews.stats_for_user.return_value = (0, None)
    questions.topic_stats_for_user.return_value = []

    stats = await service.get_stats(user_id)

    assert stats.total_interviews == 0
    assert stats.average_score is None
    assert stats.best_topics == []
    assert stats.weak_topics == []


async def test_best_and_weak_topics_are_capped_at_top_three():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interviews.stats_for_user.return_value = (10, 6.0)
    questions.topic_stats_for_user.return_value = [(f"topic-{i}", float(i)) for i in range(10)]

    stats = await service.get_stats(user_id)

    assert len(stats.best_topics) == 3
    assert len(stats.weak_topics) == 3
    assert stats.best_topics[0].topic == "topic-9"
    assert stats.weak_topics[0].topic == "topic-0"
