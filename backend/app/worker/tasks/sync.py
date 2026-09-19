"""平台同步任务（spec §18：Product Sync / Order Sync 由 Worker 执行）。"""

from typing import Any

from app.connectors.ecommerce.registry import get_connector
from app.connectors.factory import get_commerce_adapter
from app.modules.commerce.application.service import CommerceService
from app.modules.store.application.sync import ProductSyncService
from app.worker.registry import REGISTRY


async def sync_products(payload: dict[str, Any]) -> dict[str, Any]:
    platform = payload.get("platform", "shopify")
    limit = int(payload.get("limit", 20))
    token = payload.get("token")
    connector = get_connector(platform)
    service = ProductSyncService(connector, CommerceService(get_commerce_adapter(), token=token))
    result = await service.sync_products(limit=limit)
    return result.as_dict()


REGISTRY["sync.products"] = sync_products
