import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.redis.client import get_redis

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


async def check_postgres(engine: AsyncEngine) -> CheckResult:
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar_one()
        return CheckResult("PostgreSQL", True, version.split()[1])
    except Exception as exc:
        return CheckResult(
            "PostgreSQL",
            False,
            f"无法连接数据库：{exc}。请确认 PostgreSQL 已启动，且 DATABASE_URL 配置正确。",
        )


async def check_redis() -> CheckResult:
    try:
        info = await get_redis().info("server")
        return CheckResult("Redis", True, info.get("redis_version", "?"))
    except Exception as exc:
        return CheckResult(
            "Redis",
            False,
            f"无法连接 Redis：{exc}。请确认 Redis 已启动，且 REDIS_URL 配置正确。",
        )


async def run_startup_checks(engine: AsyncEngine, *, fail_fast: bool = True) -> list[CheckResult]:
    results = [await check_postgres(engine), await check_redis()]
    failed = [r for r in results if not r.ok]
    for r in results:
        if r.ok:
            logger.info("startup check OK: %s (%s)", r.name, r.detail)
        else:
            logger.error("startup check FAILED: %s", r.detail)
    if failed and fail_fast:
        details = "\n".join(f"  - [{r.name}] {r.detail}" for r in failed)
        raise RuntimeError(f"环境依赖检查未通过，服务拒绝启动：\n{details}")
    return results
