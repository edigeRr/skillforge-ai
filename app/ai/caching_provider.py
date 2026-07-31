import json

from app.ai.base_provider import BaseAIProvider, Evaluation, GeneratedQuestion
from app.db.redis import redis_client

CACHE_TTL_SECONDS = 60 * 60  # 1 hour
CACHE_POOL_SIZE = 20  # rotating pool of cached questions per (language, difficulty)


class CachingAIProvider(BaseAIProvider):
    """Wraps another BaseAIProvider (Decorator pattern) and caches generated
    questions in Redis, keyed by (language, difficulty), so repeated
    interviews for the same combination don't all pay for a fresh LLM call
    just to get a question. Answer evaluation is never cached - it has to
    reflect the specific answer the candidate actually gave."""

    def __init__(self, inner: BaseAIProvider) -> None:
        self._inner = inner

    async def generate_question(
        self, language: str, difficulty: str, exclude_topics: list[str]
    ) -> GeneratedQuestion:
        cache_key = f"ai:questions:{language}:{difficulty}"
        cached = await redis_client.lrange(cache_key, 0, -1)
        for raw in cached:
            candidate = json.loads(raw)
            if candidate["topic"] not in exclude_topics:
                return GeneratedQuestion(**candidate)

        generated = await self._inner.generate_question(language, difficulty, exclude_topics)
        await redis_client.lpush(
            cache_key, json.dumps({"topic": generated.topic, "question": generated.question})
        )
        await redis_client.ltrim(cache_key, 0, CACHE_POOL_SIZE - 1)
        await redis_client.expire(cache_key, CACHE_TTL_SECONDS)
        return generated

    async def evaluate_answer(self, question: str, answer: str) -> Evaluation:
        return await self._inner.evaluate_answer(question, answer)
