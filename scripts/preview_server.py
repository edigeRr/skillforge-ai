"""Preview server for the browser frontend when Postgres and Redis aren't
available (no Docker). Serves the real pages and static files from
app/web/routes.py and answers /api/v1 with an in-memory stand-in for the
backend. Requests and responses go through the real Pydantic schemas in
app/schemas, and questions and scores come from the real FakeAIProvider, so
the frontend sees the same shapes and error codes as from the real API.

Not covered: rate limits, the dashboard cache, persistence (everything is
lost on restart). Use `docker compose up` for those.

Usage:
    python scripts/preview_server.py            (http://127.0.0.1:8765)
    python scripts/preview_server.py --port 9000

POST /api/v1/dev/reset wipes all accounts and interviews.
POST /api/v1/dev/make-admin {"email": "..."} gives an account the admin role
(the stand-in for scripts/make_admin.py).
"""

import argparse
import secrets
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.fake_provider import FakeAIProvider  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.schemas.admin import (  # noqa: E402
    CreateUserRequest,
    PaginatedUsers,
    UpdateRoleRequest,
)
from app.schemas.auth import (  # noqa: E402
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.dashboard import DashboardStatsResponse, TopicStatResponse  # noqa: E402
from app.schemas.interview import (  # noqa: E402
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
from app.schemas.user import UpdateProfileRequest, UserResponse  # noqa: E402
from app.web.routes import STATIC_DIR, not_found_handler  # noqa: E402
from app.web.routes import router as pages_router  # noqa: E402

DEFAULT_PORT = 8765
ACCESS_TOKEN_SECONDS = 30 * 60
MIN_TOPIC_DATA_POINTS = 2
TOP_TOPICS_COUNT = 3

ai = FakeAIProvider()
question_count = get_settings().INTERVIEW_QUESTION_COUNT


class ApiError(Exception):
    def __init__(self, status_code: int, error_code: str, detail: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail


@dataclass
class User:
    email: str
    password: str
    name: str
    role: str = "user"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Question:
    order_index: int
    topic: str
    question: str
    id: UUID = field(default_factory=uuid4)
    answer: str | None = None
    feedback: str | None = None
    score: float | None = None


@dataclass
class Interview:
    user_id: UUID
    language: str
    difficulty: str
    id: UUID = field(default_factory=uuid4)
    status: str = "in_progress"
    score: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    questions: list[Question] = field(default_factory=list)


@dataclass
class Store:
    users: dict[str, User] = field(default_factory=dict)
    access_tokens: dict[str, UUID] = field(default_factory=dict)
    refresh_tokens: dict[str, UUID] = field(default_factory=dict)
    interviews: dict[UUID, Interview] = field(default_factory=dict)


store = Store()
bearer_scheme = HTTPBearer(auto_error=False)


def issue_tokens(user_id: UUID) -> TokenResponse:
    access_token = secrets.token_urlsafe(24)
    refresh_token = secrets.token_urlsafe(32)
    store.access_tokens[access_token] = user_id
    store.refresh_tokens[refresh_token] = user_id
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_SECONDS,
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    user_id = store.access_tokens.get(credentials.credentials) if credentials else None
    user = next((u for u in store.users.values() if u.id == user_id), None)
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Could not validate credentials.")
    return user


def owned_interview(interview_id: UUID, user: User) -> Interview:
    interview = store.interviews.get(interview_id)
    if interview is None or interview.user_id != user.id:
        raise ApiError(404, "NOT_FOUND", "Interview not found.")
    return interview


def require_in_progress(interview: Interview) -> None:
    if interview.status != "in_progress":
        raise ApiError(409, "INTERVIEW_NOT_IN_PROGRESS", "This interview is no longer in progress.")


async def ask_next_question(interview: Interview) -> Question:
    asked = [q.topic for q in interview.questions]
    generated = await ai.generate_question(interview.language, interview.difficulty, asked)
    question = Question(
        order_index=len(interview.questions) + 1, topic=generated.topic, question=generated.question
    )
    interview.questions.append(question)
    return question


def complete(interview: Interview) -> None:
    scores = [q.score for q in interview.questions if q.score is not None]
    interview.score = round(sum(scores) / len(scores), 2) if scores else None
    interview.status = "completed"
    interview.finished_at = datetime.now(UTC)


def to_question(question: Question) -> QuestionResponse:
    return QuestionResponse.model_validate(question, from_attributes=True)


def to_detail(interview: Interview) -> InterviewDetailResponse:
    return InterviewDetailResponse(
        id=interview.id,
        language=interview.language,
        difficulty=interview.difficulty,
        status=interview.status,
        score=interview.score,
        created_at=interview.created_at,
        finished_at=interview.finished_at,
        total_questions=question_count,
        questions=[
            QuestionDetailResponse.model_validate(q, from_attributes=True)
            for q in interview.questions
        ],
    )


auth = APIRouter(prefix="/auth")


@auth.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> User:
    if payload.email in store.users:
        raise ApiError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists.")
    user = User(email=payload.email, password=payload.password, name=payload.name)
    store.users[user.email] = user
    return user


@auth.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    user = store.users.get(payload.email)
    if user is None or user.password != payload.password:
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid email or password.")
    return issue_tokens(user.id)


@auth.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    user_id = store.refresh_tokens.pop(payload.refresh_token, None)
    if user_id is None:
        raise ApiError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired.")
    return issue_tokens(user_id)


@auth.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest) -> None:
    store.refresh_tokens.pop(payload.refresh_token, None)


profile = APIRouter(prefix="/profile")


@profile.get("/me", response_model=UserResponse)
async def get_profile(user: User = Depends(current_user)) -> User:
    return user


@profile.put("/me", response_model=UserResponse)
async def update_profile(payload: UpdateProfileRequest, user: User = Depends(current_user)) -> User:
    user.name = payload.name
    return user


interviews = APIRouter(prefix="/interviews")


@interviews.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(
    payload: StartInterviewRequest, user: User = Depends(current_user)
) -> InterviewResponse:
    if any(i.user_id == user.id and i.status == "in_progress" for i in store.interviews.values()):
        raise ApiError(
            409, "INTERVIEW_ALREADY_IN_PROGRESS", "You already have an interview in progress."
        )
    interview = Interview(user_id=user.id, language=payload.language, difficulty=payload.difficulty)
    store.interviews[interview.id] = interview
    question = await ask_next_question(interview)
    return InterviewResponse(
        id=interview.id,
        language=interview.language,
        difficulty=interview.difficulty,
        status=interview.status,
        total_questions=question_count,
        current_question=to_question(question),
    )


@interviews.post("/{interview_id}/answer", response_model=AnswerResponse)
async def answer_question(
    interview_id: UUID, payload: AnswerRequest, user: User = Depends(current_user)
) -> AnswerResponse:
    interview = owned_interview(interview_id, user)
    require_in_progress(interview)
    question = next((q for q in interview.questions if q.id == payload.question_id), None)
    if question is None:
        raise ApiError(404, "NOT_FOUND", "Question not found.")
    if question.answer is not None:
        raise ApiError(409, "QUESTION_ALREADY_ANSWERED", "This question has already been answered.")

    evaluation = await ai.evaluate_answer(question.question, payload.answer)
    question.answer = payload.answer
    question.feedback = evaluation.feedback
    question.score = evaluation.score

    next_question = None
    if len(interview.questions) >= question_count:
        complete(interview)
    else:
        next_question = to_question(await ask_next_question(interview))

    return AnswerResponse(
        feedback=evaluation.feedback,
        score=evaluation.score,
        next_question=next_question,
        interview_status=interview.status,
    )


@interviews.post("/{interview_id}/finish", response_model=InterviewDetailResponse)
async def finish_interview(
    interview_id: UUID, user: User = Depends(current_user)
) -> InterviewDetailResponse:
    interview = owned_interview(interview_id, user)
    require_in_progress(interview)
    complete(interview)
    return to_detail(interview)


@interviews.get("/{interview_id}", response_model=InterviewDetailResponse)
async def get_interview(
    interview_id: UUID, user: User = Depends(current_user)
) -> InterviewDetailResponse:
    return to_detail(owned_interview(interview_id, user))


@interviews.get("", response_model=PaginatedInterviews)
async def list_interviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    language: Language | None = Query(None),
    difficulty: Difficulty | None = Query(None),
    status: InterviewStatus | None = Query(None),
    user: User = Depends(current_user),
) -> PaginatedInterviews:
    matching = [
        i
        for i in store.interviews.values()
        if i.user_id == user.id
        and (language is None or i.language == language)
        and (difficulty is None or i.difficulty == difficulty)
        and (status is None or i.status == status)
    ]
    matching.sort(key=lambda i: i.created_at, reverse=True)
    start = (page - 1) * page_size
    return PaginatedInterviews(
        items=[
            InterviewSummaryResponse.model_validate(i, from_attributes=True)
            for i in matching[start : start + page_size]
        ],
        page=page,
        page_size=page_size,
        total=len(matching),
    )


dashboard = APIRouter(prefix="/dashboard")


@dashboard.get("/stats", response_model=DashboardStatsResponse)
async def dashboard_stats(user: User = Depends(current_user)) -> DashboardStatsResponse:
    mine = [i for i in store.interviews.values() if i.user_id == user.id]
    completed_scores = [i.score for i in mine if i.status == "completed" and i.score is not None]
    completed_count = sum(1 for i in mine if i.status == "completed")

    by_topic: dict[str, list[float]] = {}
    for interview in mine:
        for question in interview.questions:
            if question.score is not None:
                by_topic.setdefault(question.topic, []).append(question.score)
    topic_stats = [
        TopicStatResponse(topic=topic, average_score=round(sum(scores) / len(scores), 2))
        for topic, scores in by_topic.items()
        if len(scores) >= MIN_TOPIC_DATA_POINTS
    ]
    ranked = sorted(topic_stats, key=lambda t: t.average_score)

    return DashboardStatsResponse(
        total_interviews=completed_count,
        average_score=(
            round(sum(completed_scores) / len(completed_scores), 2) if completed_scores else None
        ),
        best_topics=list(reversed(ranked))[:TOP_TOPICS_COUNT],
        weak_topics=ranked[:TOP_TOPICS_COUNT],
    )


def current_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise ApiError(403, "ADMIN_REQUIRED", "Administrator access required.")
    return user


admin = APIRouter(prefix="/admin")


@admin.get("/users", response_model=PaginatedUsers)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(current_admin),
) -> PaginatedUsers:
    users = sorted(store.users.values(), key=lambda u: u.created_at, reverse=True)
    start = (page - 1) * page_size
    return PaginatedUsers(
        items=[
            UserResponse.model_validate(u, from_attributes=True)
            for u in users[start : start + page_size]
        ],
        page=page,
        page_size=page_size,
        total=len(users),
    )


@admin.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, _: User = Depends(current_admin)) -> User:
    if payload.email in store.users:
        raise ApiError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists.")
    user = User(
        email=payload.email, password=payload.password, name=payload.name, role=payload.role
    )
    store.users[user.email] = user
    return user


@admin.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: UUID, payload: UpdateRoleRequest, me: User = Depends(current_admin)
) -> User:
    if user_id == me.id:
        raise ApiError(
            409, "CANNOT_CHANGE_OWN_ROLE", "Administrators cannot change their own role."
        )
    user = next((u for u in store.users.values() if u.id == user_id), None)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "User not found.")
    user.role = payload.role
    return user


dev = APIRouter(prefix="/dev")


@dev.post("/reset")
async def reset() -> dict[str, bool]:
    global store
    store = Store()
    return {"ok": True}


@dev.post("/make-admin")
async def make_admin(payload: dict[str, str]) -> dict[str, bool]:
    user = store.users.get(payload.get("email", ""))
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", "User not found.")
    user.role = "admin"
    return {"ok": True}


def create_app() -> FastAPI:
    app = FastAPI(title="SkillForge AI preview")

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": exc.error_code},
        )

    app.add_exception_handler(StarletteHTTPException, not_found_handler)

    api = APIRouter(prefix="/api/v1")
    for router in (auth, profile, interviews, dashboard, admin, dev):
        api.include_router(router)
    app.include_router(api)
    app.include_router(pages_router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
