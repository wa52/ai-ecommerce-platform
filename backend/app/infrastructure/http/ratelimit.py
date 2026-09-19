"""登录限流（spec §48 Rate Limit）。

基于 Redis 的滑动窗口计数；Redis 不可用时降级为放行（不阻断业务），并记录告警。
"""

import logging

from app.infrastructure.redis.client import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, *, limit: int, window_seconds: int, prefix: str):
        self.limit = limit
        self.window = window_seconds
        self.prefix = prefix

    async def check(self, key: str) -> tuple[bool, int]:
        """返回 (是否允许, 剩余次数)。"""
        redis_key = f"ratelimit:{self.prefix}:{key}"
        try:
            client = get_redis()
            current = await client.incr(redis_key)
            if current == 1:
                await client.expire(redis_key, self.window)
            remaining = max(0, self.limit - current)
            return current <= self.limit, remaining
        except Exception as exc:  # noqa: BLE001 - 限流不可用不应阻断业务
            logger.warning("rate limiter unavailable: %s", type(exc).__name__)
            return True, self.limit
