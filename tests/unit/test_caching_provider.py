from unittest.mock import AsyncMock

from app.ai.base_provider import Evaluation, GeneratedQuestion
from app.ai.caching_provider import CachingAIProvider


async def test_first_call_hits_inner_provider_and_caches():
    inner = AsyncMock()
    inner.generate_question.return_value = GeneratedQuestion(topic="arrays", question="Q1")
    provider = CachingAIProvider(inner)

    result = await provider.generate_question("python", "junior", [])

    assert result.topic == "arrays"
    inner.generate_question.assert_awaited_once()


async def test_second_call_for_same_key_uses_cache_not_inner():
    inner = AsyncMock()
    inner.generate_question.return_value = GeneratedQuestion(topic="arrays", question="Q1")
    provider = CachingAIProvider(inner)

    await provider.generate_question("python", "junior", [])
    result = await provider.generate_question("python", "junior", [])

    assert result.topic == "arrays"
    inner.generate_question.assert_awaited_once()  # second call was served from cache


async def test_falls_back_to_inner_when_all_cached_topics_excluded():
    inner = AsyncMock()
    inner.generate_question.side_effect = [
        GeneratedQuestion(topic="arrays", question="Q1"),
        GeneratedQuestion(topic="recursion", question="Q2"),
    ]
    provider = CachingAIProvider(inner)

    await provider.generate_question("python", "junior", [])
    result = await provider.generate_question("python", "junior", exclude_topics=["arrays"])

    assert result.topic == "recursion"
    assert inner.generate_question.await_count == 2


async def test_different_language_or_difficulty_is_not_shared_cache():
    inner = AsyncMock()
    inner.generate_question.side_effect = [
        GeneratedQuestion(topic="arrays", question="Q1"),
        GeneratedQuestion(topic="collections", question="Q2"),
    ]
    provider = CachingAIProvider(inner)

    await provider.generate_question("python", "junior", [])
    await provider.generate_question("java", "junior", [])

    assert inner.generate_question.await_count == 2


async def test_evaluate_answer_always_delegates_and_is_never_cached():
    inner = AsyncMock()
    inner.evaluate_answer.return_value = Evaluation(score=7.0, feedback="ok")
    provider = CachingAIProvider(inner)

    await provider.evaluate_answer("q", "answer one")
    await provider.evaluate_answer("q", "answer two")

    assert inner.evaluate_answer.await_count == 2
