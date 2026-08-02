from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.redis import check_redis_connection
from app.db.session import check_db_connection

router = APIRouter()


@router.get("/health", tags=["health"], summary="Health check")
async def health() -> JSONResponse:
    """No auth required. Checks live connectivity to Postgres and Redis,
    not just that the process is running - returns 503 if either is
    unreachable."""
    db_ok = await check_db_connection()
    redis_ok = await check_redis_connection()
    healthy = db_ok and redis_ok
    payload = {
        "status": "ok" if healthy else "degraded",
        "db": "ok" if db_ok else "unavailable",
        "redis": "ok" if redis_ok else "unavailable",
    }
    return JSONResponse(status_code=200 if healthy else 503, content=payload)
