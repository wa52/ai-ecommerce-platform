"""向 Saleor 写入一组可重复执行的演示商品。

前置：
1. Saleor 已启动并完成 migrate；
2. 已创建管理员；
3. 已运行 saleor_bootstrap.py，存在 default-type / Size=M。

用法：
  $env:SALEOR_ADMIN_EMAIL = "admin@example.com"
  $env:SALEOR_ADMIN_PASSWORD = "..."
  python backend/scripts/saleor_demo_products.py

脚本默认生成 100 条商品，只通过 Saleor GraphQL 操作，不直接写 Saleor 数据库。
按 slug 和 SKU 幂等，重复执行会补齐发布、价格和库存，但不会创建重复商品。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


SALEOR = os.environ.get("SALEOR_API_URL", "http://localhost:8000/graphql/")
EMAIL = os.environ.get("SALEOR_ADMIN_EMAIL")
PASSWORD = os.environ.get("SALEOR_ADMIN_PASSWORD")
CHANNEL_SLUG = os.environ.get("SALEOR_CHANNEL_SLUG", "default-channel")
PRODUCT_TYPE_SLUG = os.environ.get("SALEOR_DEFAULT_PRODUCT_TYPE_SLUG", "default-type")
CATEGORY_SLUG = os.environ.get("SALEOR_DEFAULT_CATEGORY_SLUG", "demo")
PUBLIC_ASSET_BASE_URL = os.environ.get("DEMO_PUBLIC_ASSET_BASE_URL", "http://storefront:3000")


@dataclass(frozen=True)
class DemoProduct:
    name: str
    slug: str
    sku: str
    description: str
    price: str
    quantity: int


DEMO_PRODUCT_TEMPLATES = (
    ("活着", "huo-zhe", "余华代表作，以平实克制的语言讲述福贵跌宕的一生。", 39),
    ("百年孤独", "bai-nian-gu-du", "加西亚·马尔克斯经典长篇小说，魔幻现实主义文学代表作。", 59),
    ("人类简史", "ren-lei-jian-shi", "从认知革命、农业革命到科技革命，重新梳理人类文明进程。", 68),
    ("原则", "yuan-ze", "桥水基金创始人瑞·达利欧分享工作与生活中的决策原则。", 79),
    ("小王子", "xiao-wang-zi", "写给大人和孩子的温柔寓言，关于爱、责任与成长。", 32),
    ("解忧杂货店", "jie-you-za-huo-dian", "东野圭吾温暖治愈的奇幻小说，回答每一个认真写来的烦恼。", 45),
    ("置身事内", "zhi-shen-shi-nei", "理解中国政府与经济发展的通俗经济学读本。", 58),
    ("纳瓦尔宝典", "na-wa-er-bao-dian", "关于财富与幸福的思考，整理自纳瓦尔·拉维坎特的公开分享。", 49),
    ("被讨厌的勇气", "bei-tao-yan-de-yong-qi", "以对话形式介绍阿德勒心理学，讨论自由、关系与自我选择。", 42),
    ("云边有个小卖部", "yun-bian-you-ge-xiao-mai-bu", "关于故乡、亲情与成长的温暖故事。", 39),
)


def build_demo_products(count: int = 100) -> tuple[DemoProduct, ...]:
    products = []
    for index in range(1, count + 1):
        title, slug, description, base_price = DEMO_PRODUCT_TEMPLATES[(index - 1) % len(DEMO_PRODUCT_TEMPLATES)]
        products.append(
            DemoProduct(
                name=f"{title} {index:03d}",
                slug=f"demo-{slug}-{index:03d}",
                sku=f"DEMO-{index:03d}",
                description=description,
                price=f"{base_price + (index % 5) * 10:.2f}",
                quantity=30 + (index * 17) % 121,
            )
        )
    return tuple(products)


DEMO_PRODUCTS = build_demo_products()

COVER_FILES = {
    "huo-zhe": "alive.png",
    "bai-nian-gu-du": "bai-nian-gu-du.png",
    "ren-lei-jian-shi": "alive.png",
    "yuan-ze": "principles.png",
    "xiao-wang-zi": "little-prince.png",
    "jie-you-za-huo-dian": "worry-shop.png",
    "zhi-shen-shi-nei": "inside-economy.png",
    "na-wa-er-bao-dian": "naval.png",
    "bei-tao-yan-de-yong-qi": "courage.png",
    "yun-bian-you-ge-xiao-mai-bu": "cloud-town.png",
}


def gql(query: str, variables: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        SALEOR,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Saleor HTTP {exc.code}: {exc.read().decode(errors='replace')[:600]}") from exc
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"], ensure_ascii=False))
    return body["data"]


def payload_errors(payload: dict) -> str | None:
    errors = payload.get("errors") or []
    if not errors:
        return None
    return "; ".join(e.get("message") or "未知错误" for e in errors)


def editorjs(text: str) -> str:
    return json.dumps({"blocks": [{"type": "paragraph", "data": {"text": text}}]}, ensure_ascii=False)


def main() -> int:
    if not EMAIL or not PASSWORD:
        print("缺少 SALEOR_ADMIN_EMAIL / SALEOR_ADMIN_PASSWORD", file=sys.stderr)
        return 2

    auth = gql(
        "mutation Login($email: String!, $password: String!) { tokenCreate(email: $email, password: $password) { token errors { message } } }",
        {"email": EMAIL, "password": PASSWORD},
    )["tokenCreate"]
    if auth.get("errors") or not auth.get("token"):
        raise RuntimeError(f"管理员登录失败: {auth.get('errors')}")
    token = auth["token"]

    channels = gql("{ channels { id slug currencyCode } }", token=token)["channels"]
    channel = next((item for item in channels if item["slug"] == CHANNEL_SLUG), None)
    if not channel:
        raise RuntimeError(f"找不到渠道: {CHANNEL_SLUG}")

    warehouses = gql("{ warehouses(first: 50) { edges { node { id name } } } }", token=token)["warehouses"]["edges"]
    if not warehouses:
        raise RuntimeError("Saleor 没有仓库，请先在 Saleor Dashboard 创建仓库")
    warehouse = warehouses[0]["node"]

    type_edges = gql(
        """
        query ProductType($slug: String!) {
          productTypes(first: 1, filter: {slugs: [$slug]}) {
            edges { node { id variantAttributes { id slug choices(first: 50) { edges { node { id slug } } } } } }
          }
        }
        """,
        {"slug": PRODUCT_TYPE_SLUG},
        token,
    )["productTypes"]["edges"]
    if not type_edges:
        raise RuntimeError(f"找不到商品类型 {PRODUCT_TYPE_SLUG}，请先运行 saleor_bootstrap.py")
    product_type = type_edges[0]["node"]
    variant_attribute = (product_type.get("variantAttributes") or [None])[0]
    if not variant_attribute or not variant_attribute.get("choices", {}).get("edges"):
        raise RuntimeError("商品类型没有可用的变体属性值，请先运行 saleor_bootstrap.py")
    attribute_input = {
        "id": variant_attribute["id"],
        "dropdown": {"id": variant_attribute["choices"]["edges"][0]["node"]["id"]},
    }

    category_edges = gql(
        "query Category($slug: String!) { categories(first: 1, filter: {slugs: [$slug]}) { edges { node { id } } } }",
        {"slug": CATEGORY_SLUG},
        token,
    )["categories"]["edges"]
    if category_edges:
        category_id = category_edges[0]["node"]["id"]
    else:
        created_category = gql(
            "mutation Category($input: CategoryInput!) { categoryCreate(input: $input) { category { id } errors { message } } }",
            {"input": {"name": "中文书籍", "slug": CATEGORY_SLUG}},
            token,
        )["categoryCreate"]
        error = payload_errors(created_category)
        if error:
            raise RuntimeError(f"创建演示分类失败: {error}")
        category_id = created_category["category"]["id"]

    existing = gql(
        """
        query Products($slugs: [String!]) {
          products(first: 100, filter: {slugs: $slugs}) {
            edges { node { id slug media { id url alt } variants { id sku } } }
          }
        }
        """,
        {"slugs": [item.slug for item in DEMO_PRODUCTS]},
        token,
    )["products"]["edges"]
    by_slug = {edge["node"]["slug"]: edge["node"] for edge in existing}

    for item in DEMO_PRODUCTS:
        product = by_slug.get(item.slug)
        if product:
            product_id = product["id"]
            print(f"商品已存在: {item.slug}")
        else:
            created = gql(
                """
                mutation Product($input: ProductCreateInput!) {
                  productCreate(input: $input) { product { id slug } errors { message } }
                }
                """,
                {"input": {"name": item.name, "slug": item.slug, "productType": product_type["id"], "description": editorjs(item.description)}},
                token,
            )["productCreate"]
            error = payload_errors(created)
            if error:
                raise RuntimeError(f"创建商品 {item.slug} 失败: {error}")
            product_id = created["product"]["id"]
            print(f"创建商品: {item.name}")

        updated = gql(
            """
            mutation Publish($id: ID!, $input: ProductInput!) {
              productUpdate(id: $id, input: $input) { errors { message } }
            }
            """,
            {"id": product_id, "input": {"category": category_id}},
            token,
        )["productUpdate"]
        if payload_errors(updated):
            raise RuntimeError(f"绑定分类 {item.slug} 失败: {payload_errors(updated)}")

        published = gql(
            """
            mutation Publish($id: ID!, $input: ProductChannelListingUpdateInput!) {
              productChannelListingUpdate(id: $id, input: $input) { errors { message } }
            }
            """,
            {"id": product_id, "input": {"updateChannels": [{"channelId": channel["id"], "isPublished": True, "isAvailableForPurchase": True, "visibleInListings": True}]}},
            token,
        )["productChannelListingUpdate"]
        if payload_errors(published):
            raise RuntimeError(f"发布商品 {item.slug} 失败: {payload_errors(published)}")

        variants = product.get("variants", []) if product else []
        variant = next((v for v in variants if v.get("sku") == item.sku), None)
        if not variant:
            created_variant = gql(
                """
                mutation Variant($input: ProductVariantCreateInput!) {
                  productVariantCreate(input: $input) { productVariant { id sku } errors { message } }
                }
                """,
                {"input": {"product": product_id, "sku": item.sku, "attributes": [attribute_input], "stocks": [{"warehouse": warehouse["id"], "quantity": item.quantity}]}},
                token,
            )["productVariantCreate"]
            error = payload_errors(created_variant)
            if error:
                raise RuntimeError(f"创建 SKU {item.sku} 失败: {error}")
            variant = created_variant["productVariant"]
            print(f"  创建 SKU: {item.sku}")

        listing = gql(
            """
            mutation Price($id: ID!, $input: [ProductVariantChannelListingAddInput!]!) {
              productVariantChannelListingUpdate(id: $id, input: $input) { errors { message } }
            }
            """,
            {"id": variant["id"], "input": [{"channelId": channel["id"], "price": item.price}]},
            token,
        )["productVariantChannelListingUpdate"]
        if payload_errors(listing):
            raise RuntimeError(f"设置价格 {item.sku} 失败: {payload_errors(listing)}")

        stock = gql(
            """
            mutation Stock($variantId: ID!, $stocks: [StockInput!]!) {
              productVariantStocksUpdate(variantId: $variantId, stocks: $stocks) { errors { message } }
            }
            """,
            {"variantId": variant["id"], "stocks": [{"warehouse": warehouse["id"], "quantity": item.quantity}]},
            token,
        )["productVariantStocksUpdate"]
        if payload_errors(stock):
            raise RuntimeError(f"设置库存 {item.sku} 失败: {payload_errors(stock)}")

        cover_key = next((key for key in COVER_FILES if item.slug.startswith(f"demo-{key}-")), None)
        existing_media = (product or {}).get("media", [])
        # 清理早期导入留下的失效缩略图，避免前端收到 404 的 thumbnail URL。
        broken_media = [m for m in existing_media if "/thumbnail/" in str(m.get("url", ""))]
        for media_item in broken_media:
            deleted = gql(
                """
                mutation DeleteMedia($id: ID!) {
                  productMediaDelete(id: $id) { errors { message } }
                }
                """,
                {"id": media_item["id"]},
                token,
            )["productMediaDelete"]
            error = payload_errors(deleted)
            if error:
                raise RuntimeError(f"清理失效封面 {item.slug} 失败: {error}")
        if broken_media:
            existing_media = [m for m in existing_media if m not in broken_media]
        if cover_key and not existing_media:
            media = gql(
                """
                mutation Media($input: ProductMediaCreateInput!) {
                  productMediaCreate(input: $input) { media { id url } errors { message } }
                }
                """,
                {
                    "input": {
                        "product": product_id,
                        "mediaUrl": f"{PUBLIC_ASSET_BASE_URL.rstrip('/')}/book-covers/{COVER_FILES[cover_key]}",
                        "alt": item.name,
                    }
                },
                token,
            )["productMediaCreate"]
            error = payload_errors(media)
            if error:
                raise RuntimeError(f"设置封面 {item.slug} 失败: {error}")
            print(f"  设置封面: {COVER_FILES[cover_key]}")

    print(f"DEMO PRODUCTS: PASS ({len(DEMO_PRODUCTS)} items, channel={CHANNEL_SLUG}, warehouse={warehouse['name']})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, urllib.error.URLError) as exc:
        print(f"DEMO PRODUCTS: FAIL | {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
