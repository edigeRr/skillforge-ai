from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.ai.factory import get_ai_provider
from app.api.deps import get_current_user, get_interview_repository, get_question_repository
from app.core.rate_limit import general_write_rate_limit
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from app.repositories.interview_repository import InterviewRepository
from app.repositories.question_repository import QuestionRepository
from app.schemas.interview import (
    AnswerRequest,
    AnswerResponse,
    Difficulty,
    InterviewDetailResponse,
    InterviewResponse,
    InterviewStatus,
    InterviewSummaryResponse,
    Language,
    PaginatedInterviews,
    QuestionDetailResponse,
    QuestionResponse,
    StartInterviewRequest,
)
from app.services.interview_service import InterviewService

router = APIRouter()


def get_interview_service(
    interviews: InterviewRepository = Depends(get_interview_repository),
    questions: QuestionRepository = Depends(get_question_repository),
) -> InterviewService:
    return InterviewService(interviews, questions, get_ai_provider())


def _to_detail(interview: Interview, questions: list[Question]) -> InterviewDetailResponse:
    return InterviewDetailResponse(
        id=interview.id,
        language=interview.language,
        difficulty=interview.difficulty,
        status=interview.status,
        score=interview.score,
        created_at=interview.created_at,
        finished_at=interview.finished_at,
        questions=[QuestionDetailResponse.model_validate(q) for q in questions],
    )


# How to verify starting an interview
# ===================================
#
# 1. In the browser (start the app as in the registration block in app/api/v1/auth.py)
#    Create an account at /register. Expected: you land on /interview with the start form.
#    Press "Start interview" without choosing anything. Expected: the browser asks you to
#    pick a language; nothing is sent. Choose a language and a level and press it again.
#    Expected: you land on /interview/<id>, a placeholder until the session screen exists.
#    Go back to /interview and start another one. Expected: "You already have an interview
#    in progress" with a "Continue that interview" button that opens the same /interview/<id>.
#
# 2. Straight against the API (macOS, Linux, Git Bash), with the access_token from login
#      curl -i -X POST http://localhost:8000/api/v1/interviews \
#        -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
#        -d '{"language": "python", "difficulty": "junior"}'
#    Expected: 201 with the interview id and current_question. Repeat it: 409
#    INTERVIEW_ALREADY_IN_PROGRESS. Then find the open one:
#      curl -H "Authorization: Bearer <access_token>" \
#        "http://localhost:8000/api/v1/interviews?status=in_progress&page_size=1"
#    Expected: one item with the same id. Send "language": "rust": 422. Leave out the
#    Authorization header: 401.
#
#    Windows PowerShell:
#      Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/interviews `
#        -Headers @{ Authorization = "Bearer <access_token>" } `
#        -ContentType "application/json" -Body '{"language": "python", "difficulty": "junior"}'
#
# 3. Automated tests (same test database as in the registration block)
#      pytest tests/integration/test_interview_flow.py tests/integration/test_pages.py -q
#      cd tests-frontend
#      npm test


@router.post(
    "",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Start an interview",
)
async def start_interview(
    payload: StartInterviewRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewService = Depends(get_interview_service),
) -> InterviewResponse:
    """Start a new interview and get the first question in the same
    response. A user can only have one interview `in_progress` at a time -
    finish or complete the current one before starting another
    (`409 INTERVIEW_ALREADY_IN_PROGRESS`)."""
    interview, question = await service.start(current_user.id, payload.language, payload.difficulty)
    return InterviewResponse(
        id=interview.id,
        language=interview.language,
        difficulty=interview.difficulty,
        status=interview.status,
        current_question=QuestionResponse.model_validate(question),
    )


@router.post(
    "/{interview_id}/answer",
    response_model=AnswerResponse,
    dependencies=[Depends(general_write_rate_limit)],
    summary="Submit an answer",
)
async def answer_question(
    interview_id: UUID,
    payload: AnswerRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewService = Depends(get_interview_service),
) -> AnswerResponse:
    """Answer the current question. Returns a score, written feedback, and
    either the next question or `interview_status: "completed"` once the
    session's question count is reached."""
    result = await service.answer(
        current_user.id, interview_id, payload.question_id, payload.answer
    )
    return AnswerResponse(
        feedback=result.feedback,
        score=result.score,
        next_question=(
            QuestionResponse.model_validate(result.next_question) if result.next_question else None
        ),
        interview_status=result.interview_status,
    )


@router.post(
    "/{interview_id}/finish",
    response_model=InterviewDetailResponse,
    dependencies=[Depends(general_write_rate_limit)],
    summary="End an interview early",
)
async def finish_interview(
    interview_id: UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    """Mark the interview completed before all questions are answered. The
    overall score is computed from answered questions only."""
    interview = await service.finish(current_user.id, interview_id)
    _, questions = await service.get_detail(current_user.id, interview_id)
    return _to_detail(interview, questions)


@router.get("/{interview_id}", response_model=InterviewDetailResponse, summary="View one interview")
async def get_interview(
    interview_id: UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewService = Depends(get_interview_service),
) -> InterviewDetailResponse:
    """Full detail for a single interview: every question, your answer,
    the feedback, and the per-question and overall scores."""
    interview, questions = await service.get_detail(current_user.id, interview_id)
    return _to_detail(interview, questions)


@router.get("", response_model=PaginatedInterviews, summary="List your past interviews")
async def list_interviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    language: Language | None = Query(None),
    difficulty: Difficulty | None = Query(None),
    status: InterviewStatus | None = Query(None),
    current_user: User = Depends(get_current_user),
    interviews: InterviewRepository = Depends(get_interview_repository),
) -> PaginatedInterviews:
    """Paginated interview history, optionally filtered by language,
    difficulty, or status."""
    items, total = await interviews.list_by_user(
        current_user.id,
        page=page,
        page_size=page_size,
        language=language,
        difficulty=difficulty,
        status=status,
    )
    return PaginatedInterviews(
        items=[InterviewSummaryResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
