from redis.asyncio import Redis, from_url

from app.core.config import get_settings

settings = get_settings()

redis_client: Redis = from_url(settings.REDIS_URL, decode_responses=True)


async def check_redis_connection() -> bool:
    try:
        return bool(await redis_client.ping())
    except Exception:
        return False
