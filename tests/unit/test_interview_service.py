from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.fake_provider import FakeAIProvider
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models.interview import Interview
from app.models.question import Question
from app.services.interview_service import InterviewService

settings = get_settings()


def make_service():
    interviews = AsyncMock()
    questions = AsyncMock()
    service = InterviewService(interviews, questions, FakeAIProvider())
    return service, interviews, questions


def make_interview(**overrides) -> Interview:
    # status has a DB server_default, not a Python-side one, so a bare
    # Interview(...) built in memory (never flushed) has status=None. Tests
    # that need an active interview must set it explicitly.
    defaults = dict(
        id=uuid4(), user_id=uuid4(), language="python", difficulty="junior", status="in_progress"
    )
    defaults.update(overrides)
    return Interview(**defaults)


async def test_start_rejects_when_an_interview_is_already_active():
    service, interviews, _ = make_service()
    interviews.get_active_for_user.return_value = make_interview()

    with pytest.raises(ConflictError):
        await service.start(uuid4(), "python", "junior")


async def test_start_creates_interview_and_first_question():
    service, interviews, questions = make_service()
    interviews.get_active_for_user.return_value = None
    interview = make_interview()
    interviews.add.return_value = interview
    questions.count_by_interview.return_value = 0
    questions.add.side_effect = lambda q: q

    result_interview, question = await service.start(interview.user_id, "python", "junior")

    assert result_interview is interview
    assert question.order_index == 1
    assert question.topic
    assert question.question


async def test_answer_rejects_when_interview_belongs_to_another_user():
    service, interviews, _ = make_service()
    interview = make_interview()
    interviews.get_by_id.return_value = interview

    with pytest.raises(NotFoundError):
        await service.answer(uuid4(), interview.id, uuid4(), "some answer")


async def test_answer_rejects_when_interview_not_in_progress():
    service, interviews, _ = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id, status="completed")
    interviews.get_by_id.return_value = interview

    with pytest.raises(ConflictError):
        await service.answer(user_id, interview.id, uuid4(), "some answer")


async def test_answer_rejects_unknown_question():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id)
    interviews.get_by_id.return_value = interview
    questions.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        await service.answer(user_id, interview.id, uuid4(), "some answer")


async def test_answer_rejects_already_answered_question():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id)
    interviews.get_by_id.return_value = interview
    question = Question(
        id=uuid4(),
        interview_id=interview.id,
        order_index=1,
        topic="data-structures",
        question="...",
        answer="already answered",
    )
    questions.get_by_id.return_value = question

    with pytest.raises(ConflictError) as exc_info:
        await service.answer(user_id, interview.id, question.id, "trying again")
    assert exc_info.value.error_code == "QUESTION_ALREADY_ANSWERED"


async def test_answer_returns_next_question_when_more_remain():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id)
    interviews.get_by_id.return_value = interview
    question = Question(
        id=uuid4(),
        interview_id=interview.id,
        order_index=1,
        topic="data-structures",
        question="...",
    )
    questions.get_by_id.return_value = question
    questions.add.side_effect = lambda q: q
    questions.count_by_interview.return_value = 1
    questions.list_topics_by_interview.return_value = ["data-structures"]

    result = await service.answer(
        user_id, interview.id, question.id, "a reasonably long answer here"
    )

    assert result.interview_status == "in_progress"
    assert result.next_question is not None
    assert result.next_question.topic != "data-structures"
    interviews.add.assert_not_called()


async def test_answer_completes_interview_on_last_question():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id)
    interviews.get_by_id.return_value = interview
    question = Question(
        id=uuid4(),
        interview_id=interview.id,
        order_index=settings.INTERVIEW_QUESTION_COUNT,
        topic="x",
        question="...",
    )
    questions.get_by_id.return_value = question
    questions.add.side_effect = lambda q: q
    questions.count_by_interview.return_value = settings.INTERVIEW_QUESTION_COUNT
    questions.list_answered_by_interview.return_value = [Question(score=8.0), Question(score=6.0)]

    result = await service.answer(user_id, interview.id, question.id, "final answer")

    assert result.interview_status == "completed"
    assert result.next_question is None
    assert interview.status == "completed"
    assert interview.score == 7.0
    interviews.add.assert_awaited_once()


async def test_finish_rejects_when_not_in_progress():
    service, interviews, _ = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id, status="completed")
    interviews.get_by_id.return_value = interview

    with pytest.raises(ConflictError):
        await service.finish(user_id, interview.id)


async def test_finish_with_no_answers_leaves_score_none():
    service, interviews, questions = make_service()
    user_id = uuid4()
    interview = make_interview(user_id=user_id)
    interviews.get_by_id.return_value = interview
    questions.list_answered_by_interview.return_value = []

    result = await service.finish(user_id, interview.id)

    assert result.status == "completed"
    assert result.score is None
