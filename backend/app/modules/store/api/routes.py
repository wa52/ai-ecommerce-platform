from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.connectors.ecommerce.base import ConnectorHealth
from app.connectors.ecommerce.registry import (
    ConnectorNotConfigured,
    get_connector,
    list_platforms,
)
from app.modules.commerce.application.factory import get_commerce_service
from app.modules.commerce.application.service import CommerceError, CommerceService
from app.modules.iam.api.deps import AdminUserDep
from app.modules.store.application.sync import ProductSyncService

router = APIRouter(prefix="/connectors", tags=["connectors"])

CommerceDep = Annotated[CommerceService, Depends(get_commerce_service)]


class PlatformInfo(ConnectorHealth):
    pass


class SyncResponse(ConnectorHealth):
    pass


@router.get("/platforms")
async def platforms(_: AdminUserDep) -> list[dict]:
    return list_platforms()


@router.get("/{platform}/health")
async def connector_health(platform: str, _: AdminUserDep) -> dict:
    try:
        connector = get_connector(platform)
    except ConnectorNotConfigured as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    health = await connector.health()
    return {"platform": connector.platform, "ok": health.ok, "detail": health.detail}


@router.post("/{platform}/sync/products")
async def sync_products(
    platform: str,
    _: AdminUserDep,
    commerce: CommerceDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    try:
        connector = get_connector(platform)
    except ConnectorNotConfigured as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not getattr(connector, "configured", False):
        raise HTTPException(
            status_code=409,
            detail=f"{platform} 未配置凭据，无法执行真实同步（REAL_INTEGRATION: NOT_VERIFIED）",
        )
    service = ProductSyncService(connector, commerce)
    try:
        result = await service.sync_products(limit=limit)
    except CommerceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return result.as_dict()
