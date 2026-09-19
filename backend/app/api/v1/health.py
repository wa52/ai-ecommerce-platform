from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.factory import get_commerce_adapter
from app.infrastructure.config.checks import CheckResult, check_postgres, check_redis
from app.infrastructure.database.session import get_db
from app.infrastructure.redis.client import get_redis

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    postgres: CheckResult
    redis: CheckResult
    saleor: CheckResult


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    pg = await check_postgres(db.bind)  # type: ignore[arg-type]
    rd = await check_redis()
    saleor_result = await get_commerce_adapter().health()
    saleor = CheckResult(name="Saleor", ok=saleor_result.ok, detail=saleor_result.detail)
    status = "ok" if pg.ok and rd.ok and saleor.ok else "degraded"
    return HealthResponse(status=status, postgres=pg, redis=rd, saleor=saleor)


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def db_ping(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
