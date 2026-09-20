import json
import logging

from app.connectors.base import CommerceAdapter
from app.infrastructure.config.settings import get_settings
from app.modules.commerce.domain.models import (
    Page,
    StoreChannel,
    UnifiedOrder,
    UnifiedOrderItem,
    UnifiedProduct,
    UnifiedProductDetail,
    UnifiedProductVariant,
    UnifiedStock,
    UnifiedVariantDetail,
    UnifiedVariantStock,
)

logger = logging.getLogger(__name__)


class CommerceError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(CommerceError):
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


_CHANNELS_QUERY = """
query Channels {
  channels {
    id
    name
    slug
    currencyCode
    isActive
    defaultCountry { code }
  }
}
"""

_CUSTOMERS_QUERY = """
query Customers($first: Int!, $after: String, $search: String) {
  customers(first: $first, after: $after, filter: {search: $search}, sortBy: {field: DATE_JOINED, direction: DESC}) {
    totalCount pageInfo { hasNextPage endCursor }
    edges { node { id email firstName lastName dateJoined isActive orders { totalCount } } }
  }
}
"""

_CATEGORIES_QUERY = """
query Categories($first: Int!, $after: String) {
  categories(first: $first, after: $after) { totalCount pageInfo { hasNextPage endCursor } edges { node { id name slug level } } }
}
"""

_PRODUCTS_QUERY = """
query Products($first: Int!, $after: String, $search: String, $slugs: [String!]) {
  products(first: $first, after: $after, filter: {search: $search, slugs: $slugs}) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        name
        slug
        productType { name }
        channelListings { channel { slug } }
      }
    }
  }
}
"""

_PRODUCT_QUERY = """
query Product($id: ID, $slug: String) {
  product(id: $id, slug: $slug) {
    id
    name
    slug
    productType { name }
    channelListings { channel { slug } }
    defaultVariant { id sku }
    variants { id sku stocks { quantity warehouse { id name } } }
  }
}
"""

_VARIANT_CREATE = """
mutation CreateVariant($input: ProductVariantCreateInput!) {
  productVariantCreate(input: $input) {
    productVariant { id sku stocks { quantity warehouse { id name } } }
    errors { field message code }
  }
}
"""

_CATEGORY_BY_SLUG_QUERY = """
query CategoryBySlug($slug: String!) {
  categories(first: 1, filter: {slugs: [$slug]}) { edges { node { id name } } }
}
"""

_CATEGORY_CREATE = """
mutation CreateCategory($input: CategoryInput!) {
  categoryCreate(input: $input) { category { id name } errors { field message code } }
}
"""

_PRODUCT_UPDATE_CATEGORY = """
mutation UpdateProductCategory($id: ID!, $input: ProductInput!) {
  productUpdate(id: $id, input: $input) { product { id name } errors { field message code } }
}
"""

_PRODUCT_CHANNEL_PUBLISH = """
mutation PublishProduct($id: ID!, $input: ProductChannelListingUpdateInput!) {
  productChannelListingUpdate(id: $id, input: $input) {
    product { id }
    errors { field message code }
  }
}
"""

_VARIANT_CHANNEL_UPDATE = """
mutation VariantChannelListing($id: ID!, $input: [ProductVariantChannelListingAddInput!]!) {
  productVariantChannelListingUpdate(id: $id, input: $input) {
    variant { id sku }
    errors { field message code }
  }
}
"""

_PRODUCT_CREATE = """
mutation CreateProduct($input: ProductCreateInput!) {
  productCreate(input: $input) {
    product { id name slug }
    errors { field message code }
  }
}
"""

_PRODUCT_UPDATE = """
mutation UpdateProduct($id: ID!, $input: ProductInput!) {
  productUpdate(id: $id, input: $input) {
    product { id name slug }
    errors { field message code }
  }
}
"""

_PRODUCT_DELETE = """
mutation DeleteProduct($id: ID!) {
  productDelete(id: $id) {
    product { id }
    errors { field message code }
  }
}
"""

_PRODUCT_TYPES_QUERY = """
query ProductTypes { productTypes(first: 1) { edges { node { id name } } } }
"""

_PRODUCT_TYPE_BY_SLUG_QUERY = """
query ProductTypeBySlug($slug: String!) {
  productTypes(first: 1, filter: {slugs: [$slug]}) { edges { node { id name } } }
}
"""

_PRODUCT_TYPE_OF_PRODUCT_QUERY = """
query ProductTypeOfProduct($id: ID!) {
  product(id: $id) { id productType { id name } }
}
"""

_VARIANT_ATTRIBUTES_QUERY = """
query VariantAttributes($id: ID!) {
  productType(id: $id) {
    id
    variantAttributes { id slug name inputType choices(first: 50) { edges { node { id name slug } } } }
  }
}
"""

_ORDERS_QUERY = """
query Orders($first: Int!, $after: String, $channel: ID!) {
  orders(first: $first, after: $after, filter: {channels: [$channel]}, sortBy: {field: CREATION_DATE, direction: DESC}) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        number
        status
        paymentStatus
        created
        channel { slug }
        total { gross { amount currency } }
        lines {
          id
          productName
          quantity
          variant { sku }
          unitPrice { gross { amount currency } }
        }
      }
    }
  }
}
"""

_ORDERS_ALL_QUERY = """
query OrdersAll($first: Int!, $after: String) {
  orders(first: $first, after: $after, sortBy: {field: CREATION_DATE, direction: DESC}) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id
        number
        status
        paymentStatus
        created
        channel { slug }
        total { gross { amount currency } }
        lines {
          id
          productName
          quantity
          variant { sku }
          unitPrice { gross { amount currency } }
        }
      }
    }
  }
}
"""

_ORDER_QUERY = """
query Order($id: ID!) {
  order(id: $id) {
    id
    number
    status
    paymentStatus
    created
    channel { slug }
    total { gross { amount currency } }
    lines {
      id
      productName
      quantity
      variant { sku }
      unitPrice { gross { amount currency } }
    }
  }
}
"""

_ORDER_CANCEL = """
mutation OrderCancel($id: ID!) {
  orderCancel(id: $id) { order { id number status paymentStatus created channel { slug } total { gross { amount currency } } lines { id productName quantity variant { sku } unitPrice { gross { amount currency } } } } errors { field message code } }
}
"""

_ORDER_MARK_PAID = """
mutation OrderMarkPaid($id: ID!, $reference: String) {
  orderMarkAsPaid(id: $id, transactionReference: $reference) { order { id number status paymentStatus created channel { slug } total { gross { amount currency } } lines { id productName quantity variant { sku } unitPrice { gross { amount currency } } } } errors { field message code } }
}
"""

_ORDER_FULFILL = """
mutation OrderFulfill($order: ID!, $input: OrderFulfillInput!) {
  orderFulfill(order: $order, input: $input) { fulfillment { id status } errors { field message code } }
}
"""

_WAREHOUSES_QUERY = """
query Warehouses { warehouses(first: 50) { edges { node { id name } } } }
"""

_VARIANTS_QUERY = """
query Variants($first: Int!, $after: String) {
  productVariants(first: $first, after: $after) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges { node { id sku stocks { quantity warehouse { name } } } }
  }
}
"""

_STOCK_UPDATE = """
mutation UpdateStock($variantId: ID!, $stocks: [StockInput!]!) {
  productVariantStocksUpdate(variantId: $variantId, stocks: $stocks) {
    productVariant { id sku stocks { quantity warehouse { name } } }
    errors { field message code }
  }
}
"""


def _money(value: dict | None) -> tuple[str, str]:
    gross = (value or {}).get("gross") or {}
    return str(gross.get("amount", "0")), str(gross.get("currency", ""))


def _to_editorjs(text: str) -> str:
    """Saleor 的 description 为 EditorJS 格式的 JSONString，需要包裹成 blocks。"""
    return json.dumps(
        {"blocks": [{"type": "paragraph", "data": {"text": text}}]},
        ensure_ascii=False,
    )


class CommerceService:
    """商品 / 订单 / 库存 / 店铺 的统一访问层（spec §6、§7、§9）。

    Saleor 是数据源，本层负责 DTO → 统一模型转换与业务校验。
    """

    def __init__(self, adapter: CommerceAdapter, token: str | None = None):
        self._adapter = adapter
        self._token = token

    async def _gql(self, query: str, variables: dict | None = None) -> dict:
        """所有对 Commerce Core 的查询都带上调用者令牌（最小权限透传）。"""
        return await self._adapter.graphql(query, variables, token=self._token)

    # ---------- Store ----------

    async def list_stores(self) -> list[StoreChannel]:
        data = await self._gql(_CHANNELS_QUERY)
        return [
            StoreChannel(
                id=c["id"],
                name=c["name"],
                slug=c["slug"],
                currency=c["currencyCode"],
                country=(c.get("defaultCountry") or {}).get("code"),
                is_active=bool(c.get("isActive")),
            )
            for c in data.get("channels", [])
        ]

    async def list_customers(self, *, search: str | None, first: int, after: str | None) -> tuple[list[dict], Page]:
        data = await self._gql(_CUSTOMERS_QUERY, {"first": first, "after": after, "search": search or None})
        block = data.get("customers") or {}
        info = block.get("pageInfo") or {}
        page = Page(total_count=block.get("totalCount", 0), has_next_page=bool(info.get("hasNextPage")), end_cursor=info.get("endCursor"))
        items = []
        for edge in block.get("edges", []):
            node = edge["node"]
            items.append({"id": node["id"], "email": node["email"], "first_name": node.get("firstName", ""), "last_name": node.get("lastName", ""), "date_joined": node.get("dateJoined"), "is_active": node.get("isActive", False), "order_count": (node.get("orders") or {}).get("totalCount", 0)})
        return items, page

    async def list_categories(self, *, first: int, after: str | None) -> tuple[list[dict], Page]:
        data = await self._gql(_CATEGORIES_QUERY, {"first": first, "after": after})
        block = data.get("categories") or {}
        info = block.get("pageInfo") or {}
        page = Page(total_count=block.get("totalCount", 0), has_next_page=bool(info.get("hasNextPage")), end_cursor=info.get("endCursor"))
        return [edge["node"] for edge in block.get("edges", [])], Page(total_count=block.get("totalCount", 0), has_next_page=bool(info.get("hasNextPage")), end_cursor=info.get("endCursor"))

    async def list_warehouses(self) -> list[dict]:
        data = await self._gql(_WAREHOUSES_QUERY)
        return [e["node"] for e in ((data.get("warehouses") or {}).get("edges") or [])]

    # ---------- Product ----------

    @staticmethod
    def _to_product(node: dict) -> UnifiedProduct:
        variant = node.get("defaultVariant")
        return UnifiedProduct(
            id=node["id"],
            name=node["name"],
            slug=node["slug"],
            description=node.get("description"),
            product_type=(node.get("productType") or {}).get("name"),
            channels=[c["channel"]["slug"] for c in node.get("channelListings", [])],
            variant=(
                UnifiedProductVariant(id=variant["id"], sku=variant.get("sku")) if variant else None
            ),
        )

    async def list_products(
        self, *, search: str | None, first: int, after: str | None, slug: str | None = None
    ) -> tuple[list[UnifiedProduct], Page]:
        data = await self._gql(
            _PRODUCTS_QUERY,
            {"first": first, "after": after, "search": search or None, "slugs": [slug] if slug else None},
        )
        block = data.get("products") or {}
        info = block.get("pageInfo") or {}
        page = Page(
            total_count=block.get("totalCount", 0),
            has_next_page=bool(info.get("hasNextPage")),
            end_cursor=info.get("endCursor"),
        )
        return [self._to_product(e["node"]) for e in block.get("edges", [])], page

    async def get_product(self, product_id: str) -> UnifiedProductDetail:
        data = await self._gql(_PRODUCT_QUERY, {"id": product_id})
        node = data.get("product")
        if not node:
            raise NotFoundError(f"商品不存在：{product_id}")
        base = self._to_product(node)
        variants = [
            UnifiedVariantDetail(
                id=v["id"],
                sku=v.get("sku"),
                stocks=[
                    UnifiedVariantStock(
                        warehouse_id=(s.get("warehouse") or {}).get("id", ""),
                        warehouse=(s.get("warehouse") or {}).get("name", ""),
                        quantity=s.get("quantity", 0),
                    )
                    for s in v.get("stocks", [])
                ],
            )
            for v in node.get("variants", [])
        ]
        return UnifiedProductDetail(**base.model_dump(), variants=variants)

    async def _ensure_default_category(self) -> str:
        """Saleor 要求商品必须有分类才能发布到渠道。"""
        slug = get_settings().saleor_default_category_slug
        data = await self._gql(_CATEGORY_BY_SLUG_QUERY, {"slug": slug})
        edges = ((data.get("categories") or {}).get("edges")) or []
        if edges:
            return edges[0]["node"]["id"]
        created = await self._gql(
            _CATEGORY_CREATE, {"input": {"name": get_settings().saleor_default_category_name, "slug": slug}}
        )
        payload = created.get("categoryCreate") or {}
        self._raise_on_errors(payload, "创建默认分类失败")
        return payload["category"]["id"]

    async def publish_to_channel(self, *, product_id: str, channel_id: str) -> None:
        """把商品发布到渠道（Saleor 要求商品先有分类，且发布后才能设置变体价格）。"""
        category_id = await self._ensure_default_category()
        assigned = await self._gql(
            _PRODUCT_UPDATE_CATEGORY, {"id": product_id, "input": {"category": category_id}}
        )
        self._raise_on_errors(assigned.get("productUpdate") or {}, "绑定商品分类失败")

        data = await self._gql(
            _PRODUCT_CHANNEL_PUBLISH,
            {
                "id": product_id,
                "input": {
                    "updateChannels": [
                        {
                            "channelId": channel_id,
                            "isPublished": True,
                            "isAvailableForPurchase": True,
                            "visibleInListings": True,
                        }
                    ]
                },
            },
        )
        payload = data.get("productChannelListingUpdate") or {}
        self._raise_on_errors(payload, "发布商品到渠道失败")

    async def create_variant(
        self,
        *,
        product_id: str,
        sku: str,
        channel_id: str,
        warehouse_id: str,
        price: str,
        quantity: int,
        attributes: list[dict] | None = None,
    ) -> UnifiedVariantDetail:
        if quantity < 0:
            raise CommerceError("库存数量不能为负数", status_code=422)
        # Saleor 的 ProductVariantCreateInput 不含 channelListings，
        # 价格通过 productVariantChannelListingUpdate 单独设置。
        input_data: dict = {
            "product": product_id,
            "sku": sku,
            "attributes": attributes or [],
            "stocks": [{"warehouse": warehouse_id, "quantity": quantity}],
        }
        data = await self._gql(_VARIANT_CREATE, {"input": input_data})
        payload = data.get("productVariantCreate") or {}
        self._raise_on_errors(payload, "创建 SKU 失败")
        variant = payload.get("productVariant") or {}
        variant_id = variant.get("id", "")

        listing = await self._gql(
            _VARIANT_CHANNEL_UPDATE,
            {"id": variant_id, "input": [{"channelId": channel_id, "price": price}]},
        )
        listing_payload = listing.get("productVariantChannelListingUpdate") or {}
        if listing_payload.get("errors"):
            self._raise_on_errors(listing_payload, "设置 SKU 价格失败")

        return UnifiedVariantDetail(
            id=variant_id,
            sku=variant.get("sku"),
            stocks=[
                UnifiedVariantStock(
                    warehouse_id=(s.get("warehouse") or {}).get("id", ""),
                    warehouse=(s.get("warehouse") or {}).get("name", ""),
                    quantity=s.get("quantity", 0),
                )
                for s in variant.get("stocks", [])
            ],
        )

    async def _default_product_type(self) -> str:
        settings = get_settings()
        preferred_slug = settings.saleor_default_product_type_slug
        if preferred_slug:
            data = await self._gql(_PRODUCT_TYPE_BY_SLUG_QUERY, {"slug": preferred_slug})
            edges = ((data.get("productTypes") or {}).get("edges")) or []
            if edges:
                return edges[0]["node"]["id"]
        data = await self._gql(_PRODUCT_TYPES_QUERY)
        edges = ((data.get("productTypes") or {}).get("edges")) or []
        if not edges:
            raise CommerceError("Saleor 中没有可用的 productType，无法创建商品", status_code=409)
        return edges[0]["node"]["id"]

    async def get_variant_attribute_requirements(self, product_id: str) -> dict:
        """返回商品的 productType 所需的变体属性（含可选值），供前端/调用方选择。"""
        data = await self._gql(_PRODUCT_TYPE_OF_PRODUCT_QUERY, {"id": product_id})
        product = data.get("product")
        if not product:
            raise NotFoundError(f"商品不存在：{product_id}")
        type_node = product.get("productType") or {}
        if not type_node.get("id"):
            return {"product_type": None, "attributes": []}
        attrs = await self._gql(_VARIANT_ATTRIBUTES_QUERY, {"id": type_node["id"]})
        node = attrs.get("productType") or {}
        return {
            "product_type": type_node.get("name"),
            "attributes": [
                {
                    "id": a["id"],
                    "name": a.get("name"),
                    "input_type": a.get("inputType"),
                    "values": [{"id": c["node"]["id"], "name": c["node"]["name"]} for c in (a.get("choices") or {}).get("edges", [])],
                }
                for a in (node.get("variantAttributes") or [])
            ],
        }

    async def create_product(self, *, name: str, slug: str, description: str | None) -> UnifiedProduct:
        product_type = await self._default_product_type()
        data = await self._gql(
            _PRODUCT_CREATE,
            {
                "input": {
                    "name": name,
                    "slug": slug,
                    "productType": product_type,
                    # Saleor 的 description 为 JSONString（富文本）
                    "description": _to_editorjs(description) if description else None,
                }
            },
        )
        payload = data.get("productCreate") or {}
        self._raise_on_errors(payload, "创建商品失败")
        return self._to_product(payload["product"])

    async def update_product(self, *, product_id: str, name: str | None, description: str | None) -> UnifiedProduct:
        input_data: dict = {}
        if name is not None:
            input_data["name"] = name
        if description is not None:
            input_data["description"] = _to_editorjs(description)
        if not input_data:
            raise CommerceError("没有需要更新的字段", status_code=422)
        data = await self._gql(_PRODUCT_UPDATE, {"id": product_id, "input": input_data})
        payload = data.get("productUpdate") or {}
        self._raise_on_errors(payload, "更新商品失败")
        return self._to_product(payload["product"])

    async def delete_product(self, product_id: str) -> None:
        data = await self._gql(_PRODUCT_DELETE, {"id": product_id})
        payload = data.get("productDelete") or {}
        self._raise_on_errors(payload, "删除商品失败")

    # ---------- Order ----------

    @staticmethod
    def _to_order(node: dict) -> UnifiedOrder:
        amount, currency = _money(node.get("total"))
        items = []
        for line in node.get("lines", []):
            line_amount, line_currency = _money(line.get("unitPrice"))
            items.append(
                UnifiedOrderItem(
                    id=line["id"],
                    product_name=line.get("productName") or "",
                    sku=(line.get("variant") or {}).get("sku"),
                    quantity=line.get("quantity", 0),
                    unit_amount=line_amount,
                    currency=line_currency or currency,
                )
            )
        return UnifiedOrder(
            id=node["id"],
            number=node.get("number") or "",
            status=node.get("status") or "",
            payment_status=node.get("paymentStatus") or "",
            channel=(node.get("channel") or {}).get("slug"),
            total_amount=amount,
            currency=currency,
            created_at=node.get("created") or "",
            items=items,
        )

    async def list_orders(self, *, channel: str | None, first: int, after: str | None) -> tuple[list[UnifiedOrder], Page]:
        if channel:
            data = await self._gql(_ORDERS_QUERY, {"first": first, "after": after, "channel": channel})
        else:
            data = await self._gql(_ORDERS_ALL_QUERY, {"first": first, "after": after})
        block = data.get("orders") or {}
        info = block.get("pageInfo") or {}
        page = Page(
            total_count=block.get("totalCount", 0),
            has_next_page=bool(info.get("hasNextPage")),
            end_cursor=info.get("endCursor"),
        )
        return [self._to_order(e["node"]) for e in block.get("edges", [])], page

    async def get_order(self, order_id: str) -> UnifiedOrder:
        data = await self._gql(_ORDER_QUERY, {"id": order_id})
        node = data.get("order")
        if not node:
            raise NotFoundError(f"订单不存在：{order_id}")
        return self._to_order(node)

    async def cancel_order(self, order_id: str) -> UnifiedOrder:
        data = await self._gql(_ORDER_CANCEL, {"id": order_id})
        payload = data.get("orderCancel") or {}
        self._raise_on_errors(payload, "取消订单失败")
        return self._to_order(payload["order"])

    async def mark_order_paid(self, order_id: str, transaction_reference: str | None = None) -> UnifiedOrder:
        data = await self._gql(_ORDER_MARK_PAID, {"id": order_id, "reference": transaction_reference})
        payload = data.get("orderMarkAsPaid") or {}
        self._raise_on_errors(payload, "标记支付失败")
        return self._to_order(payload["order"])

    async def fulfill_order(self, order_id: str, lines: list[dict]) -> dict:
        data = await self._gql(_ORDER_FULFILL, {"order": order_id, "input": {"lines": lines}})
        payload = data.get("orderFulfill") or {}
        self._raise_on_errors(payload, "创建发货单失败")
        return payload.get("fulfillment") or {}

    # ---------- Inventory ----------

    async def list_stock(self, *, first: int, after: str | None) -> tuple[list[UnifiedStock], Page]:
        data = await self._gql(_VARIANTS_QUERY, {"first": first, "after": after})
        block = data.get("productVariants") or {}
        info = block.get("pageInfo") or {}
        page = Page(
            total_count=block.get("totalCount", 0),
            has_next_page=bool(info.get("hasNextPage")),
            end_cursor=info.get("endCursor"),
        )
        rows: list[UnifiedStock] = []
        for edge in block.get("edges", []):
            node = edge["node"]
            for stock in node.get("stocks", []):
                rows.append(
                    UnifiedStock(
                        variant_id=node["id"],
                        sku=node.get("sku"),
                        warehouse=(stock.get("warehouse") or {}).get("name", ""),
                        quantity=stock.get("quantity", 0),
                    )
                )
        return rows, page

    async def set_stock(self, *, variant_id: str, warehouse_id: str, quantity: int) -> list[UnifiedStock]:
        if quantity < 0:
            raise CommerceError("库存数量不能为负数", status_code=422)
        data = await self._gql(
            _STOCK_UPDATE, {"variantId": variant_id, "stocks": [{"warehouse": warehouse_id, "quantity": quantity}]}
        )
        payload = data.get("productVariantStocksUpdate") or {}
        self._raise_on_errors(payload, "更新库存失败")
        variant = payload.get("productVariant") or {}
        return [
            UnifiedStock(
                variant_id=variant.get("id", variant_id),
                sku=variant.get("sku"),
                warehouse=(s.get("warehouse") or {}).get("name", ""),
                quantity=s.get("quantity", 0),
            )
            for s in variant.get("stocks", [])
        ]

    @staticmethod
    def _raise_on_errors(payload: dict, action: str) -> None:
        errors = payload.get("errors") or []
        if errors:
            detail = "; ".join(f"{e.get('field')}: {e.get('message')}" for e in errors)
            lowered = detail.lower()
            if "already exists" in lowered:
                raise CommerceError(f"{action}：{detail}", status_code=409)
            if (
                "does not exist" in lowered
                or "doesn't exist" in lowered
                or "not found" in lowered
                or "couldn't resolve" in lowered
                or "could not resolve" in lowered
                or "couldn't find" in lowered
            ):
                raise CommerceError(f"{action}：{detail}", status_code=404)
            raise CommerceError(f"{action}：{detail}", status_code=400)
        if not any(k for k in payload if k != "errors"):
            raise CommerceError(f"{action}：Saleor 未返回结果")
