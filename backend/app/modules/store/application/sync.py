"""平台同步服务（spec §40）：外部数据 → Connector → 统一模型 → Commerce Core。

幂等保证：以 external_id 派生稳定的 slug / SKU，重复同步复用已有实体。
"""

import logging
import re

from app.connectors.ecommerce.base import EcommerceConnector, ExternalProduct
from app.modules.commerce.application.service import CommerceError, CommerceService

logger = logging.getLogger(__name__)


def _slugify(value: str, prefix: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    if not base:
        base = "item"
    return f"{prefix}-{base}"[:250]


class SyncResult:
    def __init__(self, platform: str):
        self.platform = platform
        self.created = 0
        self.reused = 0
        self.failed = 0
        self.errors: list[str] = []

    def as_dict(self) -> dict:
        return {
            "platform": self.platform,
            "created": self.created,
            "reused": self.reused,
            "failed": self.failed,
            "errors": self.errors,
        }


class ProductSyncService:
    def __init__(self, connector: EcommerceConnector, commerce: CommerceService):
        self._connector = connector
        self._commerce = commerce

    async def _channel(self) -> dict:
        stores = await self._commerce.list_stores()
        if not stores:
            raise CommerceError("Commerce Core 中没有可用渠道，无法同步", status_code=409)
        return stores[0].model_dump()

    async def sync_products(self, *, limit: int = 20) -> SyncResult:
        result = SyncResult(self._connector.platform)
        channel = await self._channel()
        warehouses = await self._commerce.list_warehouses()
        warehouse_id = warehouses[0]["id"] if warehouses else None

        products, _ = await self._connector.get_products(limit=limit)
        for item in products:
            try:
                await self._upsert(item, channel, warehouse_id, result)
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{item.external_id}: {type(exc).__name__}: {exc}")
                logger.warning("sync product failed: %s", item.external_id)
        return result

    async def _upsert(self, item: ExternalProduct, channel: dict, warehouse_id: str | None, result: SyncResult) -> None:
        slug = _slugify(f"{self._connector.platform}-{item.external_id}", "ext")
        existing = await self._commerce.list_products(search=None, first=1, after=None, slug=slug)
        if existing[0]:
            result.reused += 1
            return

        product = await self._commerce.create_product(
            name=item.name or f"{self._connector.platform} {item.external_id}",
            slug=slug,
            description=item.description,
        )
        await self._commerce.publish_to_channel(product_id=product.id, channel_id=channel["id"])
        if warehouse_id:
            requirements = await self._commerce.get_variant_attribute_requirements(product.id)
            attrs = []
            for attr in requirements.get("attributes", []):
                values = attr.get("values") or []
                if values:
                    attrs.append({"id": attr["id"], "dropdown": {"id": values[0]["id"]}})
            await self._commerce.create_variant(
                product_id=product.id,
                sku=item.sku or f"{self._connector.platform}-{item.external_id}",
                channel_id=channel["id"],
                warehouse_id=warehouse_id,
                price=item.price,
                quantity=item.quantity,
                attributes=attrs,
            )
        result.created += 1
