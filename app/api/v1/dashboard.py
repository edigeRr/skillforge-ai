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


# How to verify the dashboard
# ===========================
#
# 1. In the browser (start the app as in the registration block in app/api/v1/auth.py)
#    Log in as a new user and open /dashboard. Expected: "Welcome back, <name>.", then
#    "Finish your first interview to see your stats here" and a "Start an interview" button.
#    Finish a few interviews, answering at least two questions on the same topics, and open
#    /dashboard again. Expected: the number of completed interviews, the average score on the
#    heat scale, and "Strongest topics" / "Needs work" with each topic's average. A topic
#    shows up only after two scored answers on it, and never in both lists at once.
#
# 2. Straight against the API (macOS, Linux, Git Bash)
#      curl -H "Authorization: Bearer <access_token>" \
#        http://localhost:8000/api/v1/dashboard/stats
#    Expected: 200 with total_interviews, average_score, best_topics and weak_topics.
#    Finish another interview and repeat it: the numbers change right away, because
#    completing an interview clears the 5-minute cache.
#
#    Without Docker, scripts/preview_server.py runs the same page against an in-memory API
#    (it has no cache).
#
# 3. Automated tests (same test database as in the registration block)
#      pytest tests/integration/test_dashboard_flow.py tests/unit/test_dashboard_service.py -q
#      cd tests-frontend
#      npm test


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
