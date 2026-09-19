"""Shopify Connector（spec §8）。

真实集成需要 Shopify 店铺域名 + Admin API access token。未提供凭据时
`configured` 为 False，健康检查返回未配置；验收报告据此标注
REAL_INTEGRATION: NOT_VERIFIED。
"""

import logging
from typing import Any

import httpx

from app.connectors.ecommerce.base import (
    ConnectorHealth,
    EcommerceConnector,
    ExternalInventory,
    ExternalOrder,
    ExternalOrderItem,
    ExternalProduct,
)

logger = logging.getLogger(__name__)

API_VERSION = "2024-10"

_PRODUCTS_QUERY = """
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        title
        description
        variants(first: 1) { edges { node { sku price inventoryQuantity } } }
      }
    }
  }
}
"""

_ORDERS_QUERY = """
query Orders($first: Int!, $after: String) {
  orders(first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        displayFinancialStatus
        displayFulfillmentStatus
        createdAt
        currencyCode
        currentTotalPriceSet { shopMoney { amount currencyCode } }
        lineItems(first: 50) {
          edges { node { id title sku quantity originalUnitPriceSet { shopMoney { amount currencyCode } } } }
        }
      }
    }
  }
}
"""


def _gid_to_id(gid: str) -> str:
    return gid.rsplit("/", 1)[-1] if gid else gid


class ShopifyConnector(EcommerceConnector):
    platform = "shopify"

    def __init__(self, shop_domain: str | None, access_token: str | None, timeout: float = 15.0):
        self.shop_domain = (shop_domain or "").strip()
        self.access_token = (access_token or "").strip()
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.shop_domain and self.access_token)

    @property
    def endpoint(self) -> str:
        return f"https://{self.shop_domain}/admin/api/{API_VERSION}/graphql.json"

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict:
        if not self.configured:
            raise RuntimeError("Shopify Connector 未配置（缺少店铺域名或访问令牌）")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers={
                    "X-Shopify-Access-Token": self.access_token,
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code == 401:
                raise RuntimeError("Shopify 令牌失效或权限不足（401）")
            if resp.status_code == 429:
                raise RuntimeError("Shopify 触发 Rate Limit（429）")
            if resp.status_code >= 400:
                raise RuntimeError(f"Shopify HTTP {resp.status_code}: {resp.text[:300]}")
            body = resp.json()
        if body.get("errors"):
            raise RuntimeError(f"Shopify GraphQL errors: {body['errors']}")
        return body.get("data", {})

    async def health(self) -> ConnectorHealth:
        if not self.configured:
            return ConnectorHealth(False, "未配置 Shopify 凭据（SHOPIFY_SHOP_DOMAIN / SHOPIFY_ACCESS_TOKEN）")
        try:
            data = await self._graphql("{ shop { name myshopifyDomain } }", {})
            shop = data.get("shop") or {}
            return ConnectorHealth(True, f"shop={shop.get('name')} domain={shop.get('myshopifyDomain')}")
        except Exception as exc:
            logger.warning("shopify health failed: %s", type(exc).__name__)
            return ConnectorHealth(False, f"Shopify 连接失败：{type(exc).__name__}: {exc}")

    async def get_products(self, *, limit: int = 50, cursor: str | None = None):
        data = await self._graphql(_PRODUCTS_QUERY, {"first": limit, "after": cursor})
        block = data.get("products") or {}
        products: list[ExternalProduct] = []
        for edge in block.get("edges", []):
            node = edge["node"]
            variant_edges = ((node.get("variants") or {}).get("edges")) or []
            variant = variant_edges[0]["node"] if variant_edges else {}
            products.append(
                ExternalProduct(
                    external_id=_gid_to_id(node["id"]),
                    name=node.get("title") or "",
                    sku=variant.get("sku"),
                    price=str(variant.get("price") or "0"),
                    currency="USD",
                    quantity=int(variant.get("inventoryQuantity") or 0),
                    description=node.get("description"),
                )
            )
        info = block.get("pageInfo") or {}
        return products, (info.get("endCursor") if info.get("hasNextPage") else None)

    async def get_orders(self, *, limit: int = 50, cursor: str | None = None):
        data = await self._graphql(_ORDERS_QUERY, {"first": limit, "after": cursor})
        block = data.get("orders") or {}
        orders: list[ExternalOrder] = []
        for edge in block.get("edges", []):
            node = edge["node"]
            money = ((node.get("currentTotalPriceSet") or {}).get("shopMoney")) or {}
            items = []
            for line_edge in ((node.get("lineItems") or {}).get("edges")) or []:
                line = line_edge["node"]
                unit = ((line.get("originalUnitPriceSet") or {}).get("shopMoney")) or {}
                items.append(
                    ExternalOrderItem(
                        external_id=_gid_to_id(line["id"]),
                        product_name=line.get("title") or "",
                        sku=line.get("sku"),
                        quantity=int(line.get("quantity") or 0),
                        unit_amount=str(unit.get("amount") or "0"),
                        currency=str(unit.get("currencyCode") or node.get("currencyCode") or "USD"),
                    )
                )
            orders.append(
                ExternalOrder(
                    external_id=_gid_to_id(node["id"]),
                    number=node.get("name") or "",
                    status=node.get("displayFulfillmentStatus") or "",
                    payment_status=node.get("displayFinancialStatus") or "",
                    currency=str(money.get("currencyCode") or node.get("currencyCode") or "USD"),
                    total_amount=str(money.get("amount") or "0"),
                    created_at=node.get("createdAt") or "",
                    items=items,
                )
            )
        info = block.get("pageInfo") or {}
        return orders, (info.get("endCursor") if info.get("hasNextPage") else None)

    async def get_inventory(self, *, limit: int = 50, cursor: str | None = None):
        products, next_cursor = await self.get_products(limit=limit, cursor=cursor)
        return (
            [
                ExternalInventory(external_id=p.external_id, sku=p.sku, quantity=p.quantity)
                for p in products
            ],
            next_cursor,
        )
