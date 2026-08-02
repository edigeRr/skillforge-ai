from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_interview_repository, get_question_repository
from app.models.user import User
from app.repositories.interview_repository import InterviewRepository
from app.repositories.question_repository import QuestionRepository
from app.schemas.dashboard import DashboardStatsResponse, TopicStatResponse
from app.services.dashboard_service import DashboardService

router = APIRouter()


def get_dashboard_service(
    interviews: InterviewRepository = Depends(get_interview_repository),
    questions: QuestionRepository = Depends(get_question_repository),
) -> DashboardService:
    return DashboardService(interviews, questions)


@router.get("/stats", response_model=DashboardStatsResponse, summary="View your stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardStatsResponse:
    """Total completed interviews, average score, and your strongest/weakest
    topics (a topic needs at least 2 scored answers to be surfaced - see
    requirements.md, FR-5.1). Cached for 5 minutes per user, invalidated
    the moment an interview completes."""
    stats = await service.get_stats(current_user.id)
    return DashboardStatsResponse(
        total_interviews=stats.total_interviews,
        average_score=stats.average_score,
        best_topics=[
            TopicStatResponse(topic=t.topic, average_score=t.average_score)
            for t in stats.best_topics
        ],
        weak_topics=[
            TopicStatResponse(topic=t.topic, average_score=t.average_score)
            for t in stats.weak_topics
        ],
    )
