import redis.asyncio as redis

from app.infrastructure.config.settings import get_settings

_settings = get_settings()

_pool: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(str(_settings.redis_url), decode_responses=True)
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
