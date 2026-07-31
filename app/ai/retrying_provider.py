import asyncio
import json
import logging
import time

import httpx

from app.ai.base_provider import BaseAIProvider, Evaluation, GeneratedQuestion
from app.ai.prompts import (
    ANSWER_EVALUATION_SYSTEM_PROMPT,
    QUESTION_GENERATION_SYSTEM_PROMPT,
    build_answer_evaluation_prompt,
    build_question_generation_prompt,
)
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class AIProviderError(AppException):
    status_code = 503
    error_code = "AI_PROVIDER_UNAVAILABLE"


class RetryingJSONProvider(BaseAIProvider):
    """Shared retry/backoff, latency logging, and JSON-response handling for
    HTTP-based providers (Template Method pattern). Subclasses only implement
    __init__ (build the right client) and _request_json() (build the vendor
    payload, call _post_with_retry, pull the JSON object out of the
    vendor-specific response shape) - prompts, parsing, and retries live
    here once instead of being duplicated per vendor."""

    provider_name: str = "unknown"

    def __init__(self, *, client: httpx.AsyncClient, max_retries: int = 2) -> None:
        self._client = client
        self._max_retries = max_retries

    async def generate_question(
        self, language: str, difficulty: str, exclude_topics: list[str]
    ) -> GeneratedQuestion:
        prompt = build_question_generation_prompt(language, difficulty, exclude_topics)
        data = await self._request_json(QUESTION_GENERATION_SYSTEM_PROMPT, prompt)
        try:
            return GeneratedQuestion(topic=str(data["topic"]), question=str(data["question"]))
        except (KeyError, TypeError) as exc:
            raise AIProviderError("AI provider returned an unexpected question format.") from exc

    async def evaluate_answer(self, question: str, answer: str) -> Evaluation:
        prompt = build_answer_evaluation_prompt(question, answer)
        data = await self._request_json(ANSWER_EVALUATION_SYSTEM_PROMPT, prompt)
        try:
            score = max(0.0, min(10.0, float(data["score"])))
            feedback = str(data["feedback"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AIProviderError("AI provider returned an unexpected evaluation format.") from exc
        return Evaluation(score=score, feedback=feedback)

    async def _request_json(self, system: str, user_message: str) -> dict:
        raise NotImplementedError

    async def _post_with_retry(self, path: str, payload: dict, *, model: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            start = time.monotonic()
            try:
                response = await self._client.post(path, json=payload)
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                if attempt == self._max_retries:
                    raise AIProviderError("The AI provider is temporarily unavailable.") from exc
                await asyncio.sleep(0.5 * (2**attempt))
                continue

            logger.info(
                "ai_provider_call",
                extra={
                    "provider": self.provider_name,
                    "model": model,
                    "elapsed_ms": round((time.monotonic() - start) * 1000),
                    "status_code": response.status_code,
                },
            )
            return response

        raise AIProviderError(
            "The AI provider is temporarily unavailable."
        ) from last_error  # unreachable

    @staticmethod
    def _extract_json(raw_text: str) -> dict:
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as exc:
            raise AIProviderError(
                "AI provider returned a response that wasn't valid JSON."
            ) from exc

    async def aclose(self) -> None:
        await self._client.aclose()
