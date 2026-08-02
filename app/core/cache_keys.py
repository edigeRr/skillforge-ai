from uuid import UUID


def dashboard_stats_key(user_id: UUID) -> str:
    return f"dashboard:stats:{user_id}"
