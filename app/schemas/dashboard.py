from pydantic import BaseModel


class TopicStatResponse(BaseModel):
    topic: str
    average_score: float


class DashboardStatsResponse(BaseModel):
    total_interviews: int
    average_score: float | None
    best_topics: list[TopicStatResponse]
    weak_topics: list[TopicStatResponse]
