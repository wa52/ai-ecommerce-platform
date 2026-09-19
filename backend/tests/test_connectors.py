import httpx
import pytest

from app.connectors.ecommerce.base import (
    ConnectorHealth,
    EcommerceConnector,
    ExternalInventory,
    ExternalOrder,
    ExternalOrderItem,
    ExternalProduct,
)
from app.connectors.ecommerce.shopify import ShopifyConnector
from app.connectors.ecommerce.registry import ConnectorNotConfigured, get_connector, list_platforms
from app.connectors.base import CommerceAdapter, CommerceHealth
from app.modules.commerce.application.service import CommerceService
from app.modules.store.application.sync import ProductSyncService


class FakeShopify(ShopifyConnector):
    def __init__(self):
        super().__init__("fake.myshopify.com", "token")

    async def _graphql(self, query: str, variables: dict) -> dict:
        if "products" in query:
            return {
                "products": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Product/111",
                                "title": "Shopify Widget",
                                "description": "from shopify",
                                "variants": {
                                    "edges": [
                                        {"node": {"sku": "SHP-111", "price": "12.50", "inventoryQuantity": 4}}
                                    ]
                                },
                            }
                        }
                    ],
                }
            }
        if "orders" in query:
            return {
                "orders": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Order/999",
                                "name": "#999",
                                "displayFulfillmentStatus": "UNFULFILLED",
                                "displayFinancialStatus": "PAID",
                                "createdAt": "2026-09-19T00:00:00Z",
                                "currencyCode": "USD",
                                "currentTotalPriceSet": {"shopMoney": {"amount": "25.00", "currencyCode": "USD"}},
                                "lineItems": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": "gid://shopify/LineItem/1",
                                                "title": "Shopify Widget",
                                                "sku": "SHP-111",
                                                "quantity": 2,
                                                "originalUnitPriceSet": {
                                                    "shopMoney": {"amount": "12.50", "currencyCode": "USD"}
                                                },
                                            }
                                        }
                                    ]
                                },
                            }
                        }
                    ],
                }
            }
        if "shop" in query:
            return {"shop": {"name": "Fake Shop", "myshopifyDomain": "fake.myshopify.com"}}
        raise AssertionError(f"unexpected query: {query[:60]}")


@pytest.mark.asyncio
async def test_shopify_products_mapped_to_external_model():
    connector = FakeShopify()
    products, cursor = await connector.get_products(limit=10)
    assert cursor is None
    assert products[0].external_id == "111"
    assert products[0].sku == "SHP-111"
    assert products[0].price == "12.50"
    assert products[0].quantity == 4


@pytest.mark.asyncio
async def test_shopify_orders_mapped_to_external_model():
    connector = FakeShopify()
    orders, _ = await connector.get_orders(limit=10)
    order = orders[0]
    assert order.external_id == "999"
    assert order.total_amount == "25.00"
    assert order.payment_status == "PAID"
    assert order.items[0].quantity == 2


@pytest.mark.asyncio
async def test_shopify_health_ok():
    health = await FakeShopify().health()
    assert health.ok is True
    assert "Fake Shop" in health.detail


@pytest.mark.asyncio
async def test_shopify_unconfigured_is_reported():
    connector = ShopifyConnector("", "")
    assert connector.configured is False
    health = await connector.health()
    assert health.ok is False
    assert "未配置" in health.detail
    with pytest.raises(RuntimeError):
        await connector.get_products()


@pytest.mark.asyncio
async def test_shopify_token_invalid_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"errors": "Invalid API key"})

    connector = ShopifyConnector("fake.myshopify.com", "bad-token")
    original_client = httpx.AsyncClient

    class PatchedClient(original_client):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedClient
    try:
        with pytest.raises(RuntimeError, match="401"):
            await connector.get_products()
    finally:
        httpx.AsyncClient = original_client


@pytest.mark.asyncio
async def test_shopify_rate_limit_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    connector = ShopifyConnector("fake.myshopify.com", "token")
    original_client = httpx.AsyncClient

    class PatchedClient(original_client):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedClient
    try:
        with pytest.raises(RuntimeError, match="Rate Limit"):
            await connector.get_orders()
    finally:
        httpx.AsyncClient = original_client


def test_registry_rejects_unknown_platform():
    with pytest.raises(ConnectorNotConfigured):
        get_connector("amazon")


def test_list_platforms_reports_shopify():
    platforms = list_platforms()
    assert platforms[0]["platform"] == "shopify"
    assert "configured" in platforms[0]


class FakeCommerceAdapter(CommerceAdapter):
    def __init__(self):
        self.created: list[str] = []
        self._products: dict[str, dict] = {}
        self.fail_slugs: set[str] = set()

    async def health(self) -> CommerceHealth:
        return CommerceHealth(True, "fake")

    async def graphql(self, query: str, variables: dict | None = None, token: str | None = None) -> dict:
        if "query Channels" in query:
            return {
                "channels": [
                    {
                        "id": "C1",
                        "name": "Default",
                        "slug": "default-channel",
                        "currencyCode": "USD",
                        "isActive": True,
                        "defaultCountry": {"code": "US"},
                    }
                ]
            }
        if "query Warehouses" in query:
            return {"warehouses": {"edges": [{"node": {"id": "W1", "name": "WH"}}]}}
        if "query Products" in query:
            slugs = (variables or {}).get("slugs")
            nodes = [
                {"node": {"id": p["id"], "name": p["name"], "slug": p["slug"], "productType": {"name": "Default"}, "channelListings": []}}
                for p in self._products.values()
                if not slugs or p["slug"] in slugs
            ]
            return {
                "products": {
                    "totalCount": len(nodes),
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": nodes,
                }
            }
        if "query ProductTypes" in query or "query ProductTypeBySlug" in query:
            return {"productTypes": {"edges": [{"node": {"id": "PT1", "name": "Default"}}]}}
        if "query ProductTypeOfProduct" in query:
            return {"product": {"id": variables["id"], "productType": {"id": "PT1", "name": "Default"}}}
        if "query CategoryBySlug" in query:
            return {"categories": {"edges": [{"node": {"id": "CAT1", "name": "Default"}}]}}
        if "query VariantAttributes" in query:
            return {
                "productType": {
                    "id": "PT1",
                    "variantAttributes": [
                        {"id": "A1", "slug": "size", "name": "Size", "inputType": "DROPDOWN",
                         "choices": {"edges": [{"node": {"id": "AV1", "name": "M", "slug": "m"}}]}}
                    ],
                }
            }
        if "mutation CreateProduct" in query:
            slug = variables["input"]["slug"]
            if slug in self.fail_slugs:
                raise RuntimeError(f"simulated upstream failure for {slug}")
            self.created.append(slug)
            self._products[slug] = {"id": f"P{len(self.created)}", "name": variables["input"]["name"], "slug": slug}
            return {"productCreate": {"product": {"id": f"P{len(self.created)}", "name": variables["input"]["name"], "slug": slug}, "errors": []}}
        if "mutation UpdateProductCategory" in query or "mutation PublishProduct" in query:
            key = "productUpdate" if "UpdateProductCategory" in query else "productChannelListingUpdate"
            return {key: {"product": {"id": variables.get("id", "P1")}, "errors": []}}
        if "mutation CreateVariant" in query:
            return {"productVariantCreate": {"productVariant": {"id": "V1", "sku": variables["input"]["sku"], "stocks": []}, "errors": []}}
        if "mutation VariantChannelListing" in query:
            return {"productVariantChannelListingUpdate": {"variant": {"id": "V1", "sku": "S"}, "errors": []}}
        raise AssertionError(f"unexpected query: {query[:60]}")


@pytest.mark.asyncio
async def test_sync_creates_product_and_is_idempotent():
    adapter = FakeCommerceAdapter()
    commerce = CommerceService(adapter, token="t")
    service = ProductSyncService(FakeShopify(), commerce)

    first = await service.sync_products(limit=10)
    assert first.created == 1
    assert first.failed == 0

    second = await service.sync_products(limit=10)
    assert second.reused == 1
    assert second.created == 0
    assert len(adapter.created) == 1


class _ConnectorStub(EcommerceConnector):
    platform = "stub"

    def __init__(self, products):
        self._products = products

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(True, "stub")

    async def get_products(self, *, limit: int = 50, cursor: str | None = None):
        return self._products, None

    async def get_orders(self, *, limit: int = 50, cursor: str | None = None):
        return [], None

    async def get_inventory(self, *, limit: int = 50, cursor: str | None = None):
        return [], None


def _external(external_id: str, name: str, sku: str | None = "SKU-1", price: str = "5.00"):
    return ExternalProduct(external_id=external_id, name=name, sku=sku, price=price, quantity=1)


@pytest.mark.asyncio
async def test_sync_empty_platform_data():
    service = ProductSyncService(_ConnectorStub([]), CommerceService(FakeCommerceAdapter(), token="t"))
    result = await service.sync_products(limit=10)
    assert result.as_dict() == {"platform": "stub", "created": 0, "reused": 0, "failed": 0, "errors": []}


@pytest.mark.asyncio
async def test_sync_missing_fields_uses_fallbacks():
    adapter = FakeCommerceAdapter()
    service = ProductSyncService(
        _ConnectorStub([_external("888", "", sku=None, price="0")]),
        CommerceService(adapter, token="t"),
    )
    result = await service.sync_products(limit=10)
    assert result.created == 1
    assert adapter.created == ["ext-stub-888"]


@pytest.mark.asyncio
async def test_sync_interrupted_then_resumed_is_idempotent():
    """同步中断后重新执行：已同步的不重复，未同步的补上。"""
    adapter = FakeCommerceAdapter()
    adapter.fail_slugs = {"ext-stub-a2"}
    commerce = CommerceService(adapter, token="t")
    items = [_external("a1", "First"), _external("a2", "Second"), _external("a3", "Third")]

    partial = await ProductSyncService(_ConnectorStub(items[:2]), commerce).sync_products(limit=10)
    assert partial.created == 1
    assert partial.failed == 1

    adapter.fail_slugs = set()
    resumed = await ProductSyncService(_ConnectorStub(items), commerce).sync_products(limit=10)
    assert resumed.reused == 1
    assert resumed.created == 2
    assert len(adapter.created) == 3


@pytest.mark.asyncio
async def test_shopify_platform_error_raises():
    connector = ShopifyConnector("fake.myshopify.com", "token")
    original_client = httpx.AsyncClient

    class PatchedClient(original_client):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(
                lambda request: httpx.Response(200, json={"errors": [{"message": "Throttled"}]})
            )
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedClient
    try:
        with pytest.raises(RuntimeError, match="GraphQL errors"):
            await connector.get_products()
    finally:
        httpx.AsyncClient = original_client


@pytest.mark.asyncio
async def test_shopify_network_error_raises():
    connector = ShopifyConnector("fake.myshopify.com", "token")
    original_client = httpx.AsyncClient

    class PatchedClient(original_client):  # type: ignore[misc,valid-type]
        def __init__(self, *args, **kwargs):
            def handler(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("network unreachable", request=request)

            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedClient
    try:
        with pytest.raises(httpx.ConnectError):
            await connector.get_products()
    finally:
        httpx.AsyncClient = original_client
