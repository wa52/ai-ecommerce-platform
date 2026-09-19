"""Phase 3 验收：Store / Product / Order / Inventory（spec §38、§39）。

真实调用 Saleor（经 AI 扩展层 API）。凭据从环境变量读取。
"""

import json
import os
import sys
import urllib.error
import urllib.request
from urllib.parse import quote

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
SALEOR = os.environ.get("SALEOR_API_URL", "http://localhost:8000/graphql/")
EMAIL = os.environ["IAM_ADMIN_EMAIL"]
PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]
BUYER_EMAIL = os.environ["IAM_CUSTOMER_EMAIL"]

SLUG = "phase3-acceptance-product"
BASE_NAME = "Phase 3 验收商品"

failures: list[str] = []


def http(method: str, url: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return 204, {}
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode(errors="replace")}


def api(method: str, path: str, body: dict | None = None, token: str | None = None):
    return http(method, f"{API}{path}", body, token)


def gql(query: str, variables: dict, token: str) -> dict:
    status, body = http("POST", SALEOR, {"query": query, "variables": variables}, token)
    if status != 200:
        raise RuntimeError(f"Saleor HTTP {status}: {body}")
    if body.get("errors"):
        raise RuntimeError(f"Saleor errors: {body['errors']}")
    return body["data"]


def check(name: str, condition: bool, detail: str = ""):
    print(("PASS " if condition else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not condition:
        failures.append(name)


# --- 登录 ---
status, body = api("POST", "/iam/login", {"email": EMAIL, "password": PASSWORD})
if status != 200:
    print(f"FATAL: login failed {status} {body}")
    sys.exit(1)
token = body["token"]
print("login: OK")

# --- Store（§39）---
status, stores = api("GET", "/commerce/stores", token=token)
check("list stores -> 200", status == 200 and len(stores) > 0, f"count={len(stores) if isinstance(stores, list) else '?'}")
channel = stores[0] if isinstance(stores, list) and stores else None
check("store has currency/country/status", bool(channel and channel.get("currency")), f"{channel}")

warehouses = api("GET", "/commerce/warehouses", token=token)[1]
warehouse_id = warehouses[0]["id"] if warehouses else None
check("warehouse available", bool(warehouse_id), f"id={warehouse_id}")

# --- Product 创建（§38.1）---
status, created = api(
    "POST", "/commerce/products", {"name": BASE_NAME, "slug": SLUG, "description": "验收用"}, token=token
)
if status == 409:
    products = api("GET", f"/commerce/products?slug={SLUG}", token=token)[1]["items"]
    created = next((p for p in products if p["slug"] == SLUG), None)
    print("product already exists -> reuse (idempotent re-run)")
check("create product -> 201", status in (201, 409) and bool(created), f"status={status}")
product_id = created["id"]

status, detail = api("GET", f"/commerce/products/{product_id}", token=token)
check("get product -> 200", status == 200 and detail["slug"] == SLUG, f"status={status}")

# --- SKU / Variant + 商品与库存关联（§38.1 #7 #8）---
sku = f"{SLUG}-sku1"
status, _ = api("POST", f"/commerce/products/{product_id}/publish?channel_id={channel['id']}", token=token)
check("publish product to channel -> 204", status == 204, f"status={status}")

requirements = api("GET", f"/commerce/products/{product_id}/variant-requirements", token=token)[1]
attrs_input = []
for attr in requirements.get("attributes", []):
    values = attr.get("values") or []
    if values:
        attrs_input.append({"id": attr["id"], "dropdown": {"id": values[0]["id"]}})
print("variant attributes required:", [a["name"] for a in requirements.get("attributes", [])])

status, variant = api(
    "POST",
    f"/commerce/products/{product_id}/variants",
    {
        "sku": sku,
        "channel_id": channel["id"],
        "warehouse_id": warehouse_id,
        "price": "19.99",
        "quantity": 5,
        "attributes": attrs_input,
    },
    token=token,
)
if status == 409:
    variants = api("GET", f"/commerce/products/{product_id}", token=token)[1]["variants"]
    variant = next((v for v in variants if v["sku"] == sku), None)
    print("variant already exists -> reuse (idempotent re-run)")
check("create variant -> 201", status in (201, 409) and bool(variant), f"status={status}")
variant_id = variant["id"]

status, detail = api("GET", f"/commerce/products/{product_id}", token=token)
linked = [v for v in detail.get("variants", []) if v["id"] == variant_id]
check(
    "product-variant-inventory linked",
    bool(linked) and bool(linked[0]["stocks"]) and linked[0]["stocks"][0]["quantity"] == 5,
    f"stocks={linked[0]['stocks'] if linked else None}",
)

# --- 编辑商品（§38.1 #3）---
status, updated = api("PATCH", f"/commerce/products/{product_id}", {"name": f"{BASE_NAME}（已改名）"}, token=token)
check("update product -> 200", status == 200 and updated["name"].endswith("（已改名）"), f"status={status}")

# --- 搜索与分页（§38.1 #5 #6）---
status, found = api("GET", "/commerce/products?search=Phase&first=20", token=token)
check(
    "search product -> found",
    status == 200 and found["page"]["total_count"] >= 1 and any("phase" in i["name"].lower() for i in found["items"]),
    f"count={found['page']['total_count'] if status == 200 else '?'} names={[i['name'] for i in found['items']] if status == 200 else '?'}",
)

status, page1 = api("GET", "/commerce/products?first=1", token=token)
check(
    "pagination fields present",
    status == 200 and "has_next_page" in page1["page"] and "total_count" in page1["page"],
    f"page={page1['page'] if status == 200 else '?'}",
)

# --- 库存变化（§38.3）---
status, after_inc = api(
    "POST", "/commerce/inventory", {"variant_id": variant_id, "warehouse_id": warehouse_id, "quantity": 8}, token=token
)
check("stock increase -> 8", status == 200 and after_inc[0]["quantity"] == 8, f"status={status} {after_inc}")

status, after_dec = api(
    "POST", "/commerce/inventory", {"variant_id": variant_id, "warehouse_id": warehouse_id, "quantity": 2}, token=token
)
check("stock decrease -> 2", status == 200 and after_dec[0]["quantity"] == 2, f"status={status} {after_dec}")

status, _ = api(
    "POST", "/commerce/inventory", {"variant_id": variant_id, "warehouse_id": warehouse_id, "quantity": -1}, token=token
)
check("negative stock rejected -> 422", status == 422, f"status={status}")

status, rows = api("GET", "/commerce/inventory?first=100", token=token)
trace = [r for r in rows["items"] if r["variant_id"] == variant_id]
check("stock traceable in inventory list", status == 200 and bool(trace) and trace[0]["quantity"] == 2, f"rows={trace}")

# --- Order（§38.2）：在 Saleor 侧创建真实订单 ---
ADDRESS = """
        firstName: "Phase3"
        lastName: "Buyer"
        streetAddress1: "1 Test Street"
        city: "NYC"
        postalCode: "10001"
        country: US
        countryArea: "NY"
"""

draft = gql(
    """
    mutation Draft($channelId: ID!, $email: String!, $variantId: ID!) {
      draftOrderCreate(input: {
        channelId: $channelId
        userEmail: $email
        billingAddress: {%s}
        shippingAddress: {%s}
        lines: [{ variantId: $variantId, quantity: 2 }]
      }) {
        order { id number status total { gross { amount currency } } }
        errors { field message }
      }
    }
    """
    % (ADDRESS, ADDRESS),
    {"channelId": channel["id"], "email": BUYER_EMAIL, "variantId": variant_id},
    token,
)["draftOrderCreate"]
if draft.get("errors"):
    print("draftOrderCreate errors:", draft["errors"])
draft_id = (draft.get("order") or {}).get("id")

# 选择配送方式（Saleor 完成草稿订单要求）
if draft_id:
    shipping_methods = gql(
        "query Ship($id: ID!) { order(id: $id) { shippingMethods { id name } } }",
        {"id": draft_id},
        token,
    )["order"]["shippingMethods"]
    if shipping_methods:
        selected = gql(
            "mutation SetShip($id: ID!, $method: ID!) { orderUpdateShipping(order: $id, input: {shippingMethod: $method}) { order { id } errors { field message } } }",
            {"id": draft_id, "method": shipping_methods[0]["id"]},
            token,
        )["orderUpdateShipping"]
        if selected.get("errors"):
            print("orderUpdateShipping errors:", selected["errors"])
    else:
        print("no shipping methods available")

completed = (
    gql(
        "mutation Complete($id: ID!) { draftOrderComplete(id: $id) { order { id number status total { gross { amount currency } } } errors { field message } } }",
        {"id": draft_id},
        token,
    )["draftOrderComplete"]
    if draft_id
    else {"errors": ["no draft"]}
)
if completed.get("errors"):
    print("draftOrderComplete errors:", completed["errors"])
order_id = (completed.get("order") or {}).get("id")
check("real order created in Saleor", bool(order_id), f"order_id={order_id}")

status, orders = api("GET", "/commerce/orders?first=10", token=token)
check(
    "list orders -> 200",
    status == 200 and orders["page"]["total_count"] >= 1,
    f"total={orders['page']['total_count'] if status == 200 else '?'}",
)

status, order = api("GET", f"/commerce/orders/{order_id}", token=token)
check(
    "order detail: items/amount/currency",
    status == 200 and bool(order["items"]) and order["total_amount"] not in ("", "0") and bool(order["currency"]),
    f"status={status} total={order.get('total_amount')} {order.get('currency')} items={len(order.get('items', []))}",
)
check(
    "order item has sku/quantity/unit amount",
    bool(order.get("items")) and order["items"][0]["quantity"] == 2 and bool(order["items"][0]["sku"]),
    f"item={order.get('items', [None])[0]}",
)

status, scoped = api("GET", f"/commerce/orders?channel={channel['id']}&first=5", token=token)
check("orders filtered by channel", status == 200, f"channel_id={channel['id']} total={scoped['page']['total_count'] if status == 200 else '?'}")

# --- 删除商品（§38.1 #4）---
status, _ = api("DELETE", f"/commerce/products/{product_id}", token=token)
check("delete product -> 204", status == 204, f"status={status}")
status, _ = api("GET", f"/commerce/products/{product_id}", token=token)
check("deleted product -> 404", status == 404, f"status={status}")

print()
print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
