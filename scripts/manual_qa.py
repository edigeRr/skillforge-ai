"""Manual QA helper for Sprint 4, SF-68: run a handful of full interviews
against the configured AI_PROVIDER and print each Q&A/score so a human can
eyeball question quality and scoring sanity. Not part of the automated test
suite - this calls a real LLM and costs real API credits.

Usage:
    AI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-... python scripts/manual_qa.py
    AI_PROVIDER=openai OPENAI_API_KEY=sk-... python scripts/manual_qa.py
"""

import asyncio

from app.ai.factory import get_ai_provider
from app.core.config import get_settings

settings = get_settings()

SAMPLE_ANSWERS = {
    "python": (
        "I'd use a set to track seen items while building a new list, which keeps "
        "insertion order and runs in O(n)."
    ),
    "java": (
        "ArrayList is backed by an array so random access is O(1); LinkedList is O(1) "
        "for insert/delete once you're at a node, but O(n) just to reach it."
    ),
    "cpp": (
        "unique_ptr owns the resource exclusively and can't be copied, only moved; "
        "shared_ptr uses reference counting so multiple owners can share it."
    ),
    "javascript": (
        "Microtasks (promises) run before the next macrotask (setTimeout, I/O) - after "
        "each macrotask, the microtask queue is drained completely first."
    ),
}


async def run_one(language: str, difficulty: str) -> None:
    provider = get_ai_provider()
    print(f"\n=== {language} / {difficulty} ===")
    question = await provider.generate_question(language, difficulty, exclude_topics=[])
    print(f"Q [{question.topic}]: {question.question}")

    answer = SAMPLE_ANSWERS.get(language, "A brief answer.")
    evaluation = await provider.evaluate_answer(question.question, answer)
    print(f"A: {answer}")
    print(f"Score: {evaluation.score}/10 - {evaluation.feedback}")


async def main() -> None:
    print(f"Provider: {settings.AI_PROVIDER}")
    for language in ("python", "java", "cpp", "javascript"):
        await run_one(language, "middle")


if __name__ == "__main__":
    asyncio.run(main())
