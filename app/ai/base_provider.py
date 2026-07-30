from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GeneratedQuestion:
    topic: str
    question: str


@dataclass
class Evaluation:
    score: float  # 0-10
    feedback: str


class BaseAIProvider(ABC):
    """Interface every AI backend implements, so InterviewService never talks
    to a specific vendor SDK directly (see architecture.md, section 3 - this
    is the Strategy pattern: the service depends on this interface, and the
    concrete provider is swapped via config, not by editing the service)."""

    @abstractmethod
    async def generate_question(
        self, language: str, difficulty: str, exclude_topics: list[str]
    ) -> GeneratedQuestion: ...

    @abstractmethod
    async def evaluate_answer(self, question: str, answer: str) -> Evaluation: ...
