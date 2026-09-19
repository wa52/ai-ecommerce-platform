import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.connectors.base import CommerceAdapter, CommerceHealth
from app.connectors.factory import get_commerce_adapter
from app.main import create_app
from app.modules.commerce.application.service import CommerceService
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)


class FakeCommerce(CommerceAdapter):
    def __init__(self):
        self.calls: list[tuple[str, dict | None]] = []

    async def health(self) -> CommerceHealth:
        return CommerceHealth(True, "fake")

    async def graphql(self, query: str, variables: dict | None = None, token: str | None = None) -> dict:
        self.calls.append((query, variables))
        if "query Channels" in query:
            return {
                "channels": [
                    {
                        "id": "Q2hhbm5lbDox",
                        "name": "默认渠道",
                        "slug": "default-channel",
                        "currencyCode": "USD",
                        "isActive": True,
                        "defaultCountry": {"code": "US"},
                    }
                ]
            }
        if "query Products" in query:
            return {
                "products": {
                    "totalCount": 1,
                    "pageInfo": {"hasNextPage": False, "endCursor": "c1"},
                    "edges": [
                        {
                            "node": {
                                "id": "P1",
                                "name": "测试商品",
                                "slug": "test-product",
                                "productType": {"name": "Default"},
                                "channelListings": [{"channel": {"slug": "default-channel"}}],
                            }
                        }
                    ],
                }
            }
        if "query Product(" in query:
            return {
                "product": {
                    "id": "P1",
                    "name": "测试商品",
                    "slug": "test-product",
                    "productType": {"name": "Default"},
                    "channelListings": [{"channel": {"slug": "default-channel"}}],
                    "defaultVariant": {"id": "V1", "sku": "SKU-1"},
                    "variants": [
                        {
                            "id": "V1",
                            "sku": "SKU-1",
                            "stocks": [{"quantity": 5, "warehouse": {"id": "W1", "name": "默认仓库"}}],
                        }
                    ],
                }
            }
        if "mutation CreateVariant" in query:
            input_data = variables["input"]
            return {
                "productVariantCreate": {
                    "productVariant": {
                        "id": "V2",
                        "sku": input_data["sku"],
                        "stocks": [
                            {
                                "quantity": input_data["stocks"][0]["quantity"],
                                "warehouse": {"id": "W1", "name": "默认仓库"},
                            }
                        ],
                    },
                    "errors": [],
                }
            }
        if "mutation VariantChannelListing" in query:
            return {"productVariantChannelListingUpdate": {"variant": {"id": variables["id"], "sku": "S"}, "errors": []}}
        if "mutation PublishProduct" in query:
            return {"productChannelListingUpdate": {"product": {"id": variables["id"]}, "errors": []}}
        if "query CategoryBySlug" in query:
            return {"categories": {"edges": [{"node": {"id": "CAT1", "name": "Default Category"}}]}}
        if "mutation UpdateProductCategory" in query:
            return {"productUpdate": {"product": {"id": variables["id"], "name": "x"}, "errors": []}}
        if "query ProductTypes" in query or "query ProductTypeBySlug" in query:
            return {"productTypes": {"edges": [{"node": {"id": "PT1", "name": "Default"}}]}}
        if "mutation CreateProduct" in query:
            return {"productCreate": {"product": {"id": "P2", "name": "新商品", "slug": "new-product"}, "errors": []}}
        if "mutation UpdateProduct" in query:
            return {"productUpdate": {"product": {"id": "P1", "name": "改名", "slug": "test-product"}, "errors": []}}
        if "mutation DeleteProduct" in query:
            return {"productDelete": {"product": {"id": "P1"}, "errors": []}}
        if "query Orders" in query:
            return {
                "orders": {
                    "totalCount": 1,
                    "pageInfo": {"hasNextPage": False, "endCursor": "o1"},
                    "edges": [
                        {
                            "node": {
                                "id": "O1",
                                "number": "1001",
                                "status": "UNFULFILLED",
                                "paymentStatus": "FULLY_CHARGED",
                                "created": "2026-09-19T10:00:00+00:00",
                                "channel": {"slug": "default-channel"},
                                "total": {"gross": {"amount": "99.50", "currency": "USD"}},
                                "lines": [
                                    {
                                        "id": "L1",
                                        "productName": "测试商品",
                                        "quantity": 2,
                                        "variant": {"sku": "SKU-1"},
                                        "unitPrice": {"gross": {"amount": "49.75", "currency": "USD"}},
                                    }
                                ],
                            }
                        }
                    ],
                }
            }
        if "query Order(" in query:
            return {
                "order": {
                    "id": "O1",
                    "number": "1001",
                    "status": "UNFULFILLED",
                    "paymentStatus": "FULLY_CHARGED",
                    "created": "2026-09-19T10:00:00+00:00",
                    "channel": {"slug": "default-channel"},
                    "total": {"gross": {"amount": "99.50", "currency": "USD"}},
                    "lines": [],
                }
            }
        if "query Variants" in query:
            return {
                "productVariants": {
                    "totalCount": 1,
                    "pageInfo": {"hasNextPage": False, "endCursor": "v1"},
                    "edges": [
                        {
                            "node": {
                                "id": "V1",
                                "sku": "SKU-1",
                                "stocks": [{"quantity": 5, "warehouse": {"name": "默认仓库"}}],
                            }
                        }
                    ],
                }
            }
        if "mutation UpdateStock" in query:
            return {
                "productVariantStocksUpdate": {
                    "productVariant": {
                        "id": "V1",
                        "sku": "SKU-1",
                        "stocks": [{"quantity": variables["stocks"][0]["quantity"], "warehouse": {"name": "默认仓库"}}],
                    },
                    "errors": [],
                }
            }
        if "query Warehouses" in query:
            return {"warehouses": {"edges": [{"node": {"id": "W1", "name": "默认仓库"}}]}}
        raise AssertionError(f"unexpected query: {query[:80]}")


def _client(fake: FakeCommerce) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_commerce_adapter] = lambda: fake
    from app.modules.commerce.application.factory import get_commerce_service

    app.dependency_overrides[get_commerce_service] = lambda: CommerceService(fake)
    return TestClient(app)


@pytest.mark.asyncio
async def test_product_mapping_to_unified_model():
    service = CommerceService(FakeCommerce())
    products, page = await service.list_products(search="测试", first=10, after=None)
    assert page.total_count == 1
    assert products[0].name == "测试商品"
    assert products[0].channels == ["default-channel"]


@pytest.mark.asyncio
async def test_order_mapping_amounts_and_items():
    service = CommerceService(FakeCommerce())
    orders, _ = await service.list_orders(channel=None, first=10, after=None)
    order = orders[0]
    assert order.total_amount == "99.50"
    assert order.currency == "USD"
    assert order.items[0].quantity == 2
    assert order.items[0].unit_amount == "49.75"


@pytest.mark.asyncio
async def test_set_stock_rejects_negative():
    service = CommerceService(FakeCommerce())
    with pytest.raises(Exception) as exc:
        await service.set_stock(variant_id="V1", warehouse_id="W1", quantity=-1)
    assert "负数" in str(exc.value)


def test_products_endpoint_requires_admin():
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"

    async def customer():
        return CurrentUser(id="U2", email="buyer@example.com", is_staff=False)

    app.dependency_overrides[get_current_user] = customer
    app.dependency_overrides[get_commerce_adapter] = lambda: FakeCommerce()
    client = TestClient(app)
    assert client.get("/api/v1/commerce/products").status_code == 403


def test_product_crud_endpoints():
    client = _client(FakeCommerce())
    listing = client.get("/api/v1/commerce/products?search=测试&first=5")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["slug"] == "test-product"

    created = client.post(
        "/api/v1/commerce/products",
        json={"name": "新商品", "slug": "new-product"},
    )
    assert created.status_code == 201
    assert created.json()["id"] == "P2"

    updated = client.patch("/api/v1/commerce/products/P1", json={"name": "改名"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "改名"

    assert client.delete("/api/v1/commerce/products/P1").status_code == 204


def test_product_create_validation():
    client = _client(FakeCommerce())
    bad_slug = client.post("/api/v1/commerce/products", json={"name": "x", "slug": "Bad Slug"})
    assert bad_slug.status_code == 422
    missing_name = client.post("/api/v1/commerce/products", json={"slug": "ok-slug"})
    assert missing_name.status_code == 422


def test_inventory_endpoints():
    client = _client(FakeCommerce())
    rows = client.get("/api/v1/commerce/inventory")
    assert rows.status_code == 200
    assert rows.json()["items"][0]["quantity"] == 5

    negative = client.post(
        "/api/v1/commerce/inventory",
        json={"variant_id": "V1", "warehouse_id": "W1", "quantity": -5},
    )
    assert negative.status_code == 422

    ok = client.post(
        "/api/v1/commerce/inventory",
        json={"variant_id": "V1", "warehouse_id": "W1", "quantity": 9},
    )
    assert ok.status_code == 200
    assert ok.json()[0]["quantity"] == 9


def test_stores_endpoint():
    client = _client(FakeCommerce())
    resp = client.get("/api/v1/commerce/stores")
    assert resp.status_code == 200
    assert resp.json()[0]["slug"] == "default-channel"


def test_variant_create_and_product_detail():
    client = _client(FakeCommerce())
    detail = client.get("/api/v1/commerce/products/P1")
    assert detail.status_code == 200
    assert detail.json()["variants"][0]["sku"] == "SKU-1"
    assert detail.json()["variants"][0]["stocks"][0]["quantity"] == 5

    created = client.post(
        "/api/v1/commerce/products/P1/variants",
        json={
            "sku": "SKU-2",
            "channel_id": "Q2hhbm5lbDox",
            "warehouse_id": "W1",
            "price": "19.99",
            "quantity": 3,
        },
    )
    assert created.status_code == 201
    assert created.json()["sku"] == "SKU-2"
    assert created.json()["stocks"][0]["quantity"] == 3


def test_variant_create_validation():
    client = _client(FakeCommerce())
    bad_price = client.post(
        "/api/v1/commerce/products/P1/variants",
        json={"sku": "S", "channel_id": "C", "warehouse_id": "W", "price": "abc"},
    )
    assert bad_price.status_code == 422
    negative_qty = client.post(
        "/api/v1/commerce/products/P1/variants",
        json={"sku": "S", "channel_id": "C", "warehouse_id": "W", "price": "1.00", "quantity": -1},
    )
    assert negative_qty.status_code == 422
