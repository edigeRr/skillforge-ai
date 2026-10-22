from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["python", "java", "cpp", "javascript"]
Difficulty = Literal["junior", "middle", "senior"]
InterviewStatus = Literal["in_progress", "completed", "abandoned"]


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_index: int
    topic: str
    question: str


class QuestionDetailResponse(QuestionResponse):
    answer: str | None
    feedback: str | None
    score: float | None


class StartInterviewRequest(BaseModel):
    language: Language
    difficulty: Difficulty


class InterviewResponse(BaseModel):
    id: UUID
    language: str
    difficulty: str
    status: str
    total_questions: int
    current_question: QuestionResponse


class AnswerRequest(BaseModel):
    question_id: UUID
    answer: str = Field(min_length=1)


class AnswerResponse(BaseModel):
    feedback: str
    score: float
    next_question: QuestionResponse | None
    interview_status: str


class InterviewSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    language: str
    difficulty: str
    status: str
    score: float | None
    created_at: datetime
    finished_at: datetime | None


class InterviewDetailResponse(BaseModel):
    id: UUID
    language: str
    difficulty: str
    status: str
    score: float | None
    created_at: datetime
    finished_at: datetime | None
    total_questions: int
    questions: list[QuestionDetailResponse]


class PaginatedInterviews(BaseModel):
    items: list[InterviewSummaryResponse]
    page: int
    page_size: int
    total: int
