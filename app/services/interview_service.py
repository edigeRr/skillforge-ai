from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.ai.base_provider import BaseAIProvider
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.interview import Interview
from app.models.question import Question
from app.repositories.interview_repository import InterviewRepository
from app.repositories.question_repository import QuestionRepository

settings = get_settings()


@dataclass
class AnswerResult:
    feedback: str
    score: float
    next_question: Question | None
    interview_status: str


class InterviewService:
    def __init__(
        self,
        interviews: InterviewRepository,
        questions: QuestionRepository,
        ai_provider: BaseAIProvider,
    ) -> None:
        self.interviews = interviews
        self.questions = questions
        self.ai = ai_provider

    async def start(
        self, user_id: UUID, language: str, difficulty: str
    ) -> tuple[Interview, Question]:
        active = await self.interviews.get_active_for_user(user_id)
        if active is not None:
            raise ConflictError(
                "You already have an interview in progress.",
                error_code="INTERVIEW_ALREADY_IN_PROGRESS",
            )

        try:
            interview = await self.interviews.add(
                Interview(user_id=user_id, language=language, difficulty=difficulty)
            )
        except IntegrityError as exc:
            # Two concurrent start() calls both passed the check above - the
            # partial unique index on interviews(user_id) WHERE in_progress
            # catches the race that the check alone can't.
            await self.interviews.session.rollback()
            raise ConflictError(
                "You already have an interview in progress.",
                error_code="INTERVIEW_ALREADY_IN_PROGRESS",
            ) from exc

        first_question = await self._ask_next_question(interview, exclude_topics=[])
        return interview, first_question

    async def answer(
        self, user_id: UUID, interview_id: UUID, question_id: UUID, answer_text: str
    ) -> AnswerResult:
        interview = await self._get_owned_interview(user_id, interview_id)
        if interview.status != "in_progress":
            raise ConflictError(
                "This interview is no longer in progress.", error_code="INTERVIEW_NOT_IN_PROGRESS"
            )

        question = await self.questions.get_by_id(question_id)
        if question is None or question.interview_id != interview.id:
            raise NotFoundError("Question not found.")
        if question.answer is not None:
            raise ConflictError(
                "This question has already been answered.", error_code="QUESTION_ALREADY_ANSWERED"
            )

        evaluation = await self.ai.evaluate_answer(question.question, answer_text)
        question.answer = answer_text
        question.feedback = evaluation.feedback
        question.score = evaluation.score
        question.answered_at = datetime.now(UTC)
        await self.questions.add(question)

        next_question: Question | None = None
        asked_count = await self.questions.count_by_interview(interview.id)
        if asked_count >= settings.INTERVIEW_QUESTION_COUNT:
            await self._complete(interview)
        else:
            asked_topics = await self.questions.list_topics_by_interview(interview.id)
            next_question = await self._ask_next_question(interview, exclude_topics=asked_topics)

        return AnswerResult(
            feedback=evaluation.feedback,
            score=evaluation.score,
            next_question=next_question,
            interview_status=interview.status,
        )

    async def finish(self, user_id: UUID, interview_id: UUID) -> Interview:
        interview = await self._get_owned_interview(user_id, interview_id)
        if interview.status != "in_progress":
            raise ConflictError(
                "This interview is no longer in progress.", error_code="INTERVIEW_NOT_IN_PROGRESS"
            )
        await self._complete(interview)
        return interview

    async def get_detail(
        self, user_id: UUID, interview_id: UUID
    ) -> tuple[Interview, list[Question]]:
        interview = await self._get_owned_interview(user_id, interview_id)
        questions = await self.questions.list_by_interview(interview.id)
        return interview, questions

    async def _get_owned_interview(self, user_id: UUID, interview_id: UUID) -> Interview:
        interview = await self.interviews.get_by_id(interview_id)
        if interview is None or interview.user_id != user_id:
            # 404, not 403: doesn't confirm to the caller that the interview
            # exists at all if it belongs to someone else (see api.md).
            raise NotFoundError("Interview not found.")
        return interview

    async def _ask_next_question(self, interview: Interview, exclude_topics: list[str]) -> Question:
        generated = await self.ai.generate_question(
            interview.language, interview.difficulty, exclude_topics
        )
        order_index = await self.questions.count_by_interview(interview.id) + 1
        return await self.questions.add(
            Question(
                interview_id=interview.id,
                order_index=order_index,
                topic=generated.topic,
                question=generated.question,
            )
        )

    async def _complete(self, interview: Interview) -> None:
        answered = await self.questions.list_answered_by_interview(interview.id)
        interview.score = (
            round(sum(q.score for q in answered) / len(answered), 2) if answered else None
        )
        interview.status = "completed"
        interview.finished_at = datetime.now(UTC)
        await self.interviews.add(interview)
