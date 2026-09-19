from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import CommerceAdapter
from app.connectors.factory import get_commerce_adapter
from app.infrastructure.database.session import get_db
from app.modules.analytics.application.service import AnalyticsError, AnalyticsService
from app.modules.iam.api.deps import AdminUserDep, get_bearer_token

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_service(
    adapter: CommerceAdapter = Depends(get_commerce_adapter),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(get_bearer_token),
) -> AnalyticsService:
    return AnalyticsService(adapter, db, token=token)


ServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


@router.get("/formulas")
async def formulas(_: AdminUserDep, service: ServiceDep) -> dict:
    """指标口径定义（spec §42：所有指标必须在文档中定义计算公式）。"""
    return service.formulas()


@router.get("/overview")
async def overview(
    _: AdminUserDep,
    service: ServiceDep,
    days: int = Query(default=30, ge=1, le=365),
    other_cost: str = Query(default="0", pattern=r"^\d+(\.\d{1,4})?$"),
    currency: str | None = Query(default=None, min_length=3, max_length=10),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    try:
        return await service.overview(days=days, other_cost=other_cost, currency=currency, limit=limit)
    except AnalyticsError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
