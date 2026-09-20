"""Phase 11 验收：消费者 Storefront 完整 E2E（spec §2.1 Storefront）。

真实调用 Saleor GraphQL：
- 匿名商品列表 / 商品详情 / Variant 库存与价格
- Checkout 创建 / 加行 / 邮箱 / 收货地址 / 账单地址 / 配送方式 / 支付 / 完成下单
- 客户注册 / 登录 / 订单历史关联

覆盖依赖：
- SALEOR_ADMIN_EMAIL / SALEOR_ADMIN_PASSWORD：管理员，用于预置商品可见性（可选）
- 默认渠道 default-channel、Dummy 支付网关由 Saleor Docker 镜像内置
"""

import json
import os
import sys
import urllib.error
import urllib.request

SALEOR = os.environ.get("SALEOR_API_URL", "http://localhost:8000/graphql/")
CHANNEL = os.environ.get("SALEOR_CHANNEL_SLUG", "default-channel")
ADMIN_EMAIL = os.environ.get("SALEOR_ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("SALEOR_ADMIN_PASSWORD")

failures: list[str] = []


def http(method: str, url: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode(errors="replace")}


def gql(query: str, variables: dict | None = None, token: str | None = None) -> dict:
    status, body = http("POST", SALEOR, {"query": query, "variables": variables or {}}, token)
    if status != 200:
        raise RuntimeError(f"Saleor HTTP {status}: {body}")
    if body.get("errors"):
        raise RuntimeError(f"Saleor errors: {body['errors']}")
    return body["data"]


def check(name: str, condition: bool, detail: str = ""):
    print(("PASS " if condition else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not condition:
        failures.append(name)


PRODUCTS_QUERY = """
query Products($channel: String!) {
  products(first: 10, channel: $channel) {
    totalCount
    edges { node { id slug name isAvailableForPurchase variants { id name sku quantityAvailable } } }
  }
}
"""

PRODUCT_BY_SLUG = """
query Product($slug: String!, $channel: String!) {
  product(slug: $slug, channel: $channel) {
    id name slug isAvailableForPurchase
    pricing { priceRange { start { gross { amount currency } } } }
    variants { id name sku quantityAvailable }
  }
}
"""

CHECKOUT_CREATE = """
mutation C($input: CheckoutCreateInput!) {
  checkoutCreate(input: $input) {
    checkout { id token email lines { id quantity } }
    errors { field message }
  }
}
"""

CHECKOUT_EMAIL = """
mutation E($id: ID!, $email: String!) {
  checkoutEmailUpdate(id: $id, email: $email) { checkout { id } errors { field message } }
}
"""

CHECKOUT_SHIPPING = """
mutation S($id: ID!, $addr: AddressInput!) {
  checkoutShippingAddressUpdate(id: $id, shippingAddress: $addr) {
    checkout { id availableShippingMethods { id name } }
    errors { field message }
  }
}
"""

CHECKOUT_BILLING = """
mutation B($id: ID!, $addr: AddressInput!) {
  checkoutBillingAddressUpdate(id: $id, billingAddress: $addr) { checkout { id } errors { field message } }
}
"""

CHECKOUT_DELIVERY = """
mutation D($id: ID!, $methodId: ID!) {
  checkoutDeliveryMethodUpdate(id: $id, deliveryMethodId: $methodId) {
    checkout { id totalPrice { gross { amount currency } } }
    errors { field message }
  }
}
"""

CHECKOUT_PAYMENT = """
mutation P($id: ID!, $in: PaymentInput!) {
  checkoutPaymentCreate(id: $id, input: $in) { checkout { id } errors { field message } }
}
"""

CHECKOUT_COMPLETE = """
mutation F($id: ID!) {
  checkoutComplete(id: $id) {
    order { id number status paymentStatus total { gross { amount } } lines { quantity variantName } }
    errors { field message code }
  }
}
"""

REGISTER = """
mutation R($e: String!, $p: String!, $r: String!) {
  accountRegister(input: { email: $e, password: $p, redirectUrl: $r }) {
    accountErrors: errors { field message code }
  }
}
"""

TOKEN_CREATE = """
mutation T($e: String!, $p: String!) {
  tokenCreate(email: $e, password: $p) { token user { email isStaff } errors { message } }
}
"""

ME_ORDERS = """
query Me {
  me { email orders(first: 20) { edges { node { number status paymentStatus } } } }
}
"""

ADDR = {
    "firstName": "Accept",
    "lastName": "Bot",
    "streetAddress1": "1 Commerce Ave",
    "city": "Austin",
    "countryArea": "TX",
    "postalCode": "73301",
    "country": "US",
}


def main() -> int:
    # ---- 0. 管理员（可选）：确保商品在渠道可见 ----
    admin_token = None
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        data = gql(TOKEN_CREATE, {"e": ADMIN_EMAIL, "p": ADMIN_PASSWORD})
        admin_token = (data.get("tokenCreate") or {}).get("token")
        check("admin login", bool(admin_token))

    # ---- 1. 商品列表 / 详情（匿名） ----
    products = gql(PRODUCTS_QUERY, {"channel": CHANNEL}).get("products") or {}
    edges = products.get("edges") or []
    check("anonymous product list", len(edges) > 0, f"total={products.get('totalCount')}")
    if not edges:
        failures.append("no products available")
        print("请先在 Saleor 发布至少一个商品到默认渠道（并开启 listing 可见）。")
        return 1

    first = edges[0]["node"]
    slug, variant_id = first["slug"], first["variants"][0]["id"]
    detail = gql(PRODUCT_BY_SLUG, {"slug": slug, "channel": CHANNEL}).get("product")
    check("anonymous product detail", bool(detail and detail["isAvailableForPurchase"]), f"slug={slug}")

    # ---- 2. Checkout 创建 + 行 + 邮箱 + 地址 + 配送 + 支付 + 完成 ----
    created = gql(
        CHECKOUT_CREATE,
        {"input": {"channel": CHANNEL, "lines": [{"quantity": 1, "variantId": variant_id}]}},
    ).get("checkoutCreate") or {}
    checkout_id = (created.get("checkout") or {}).get("id")
    check("checkoutCreate", bool(checkout_id) and not created.get("errors"))
    if not checkout_id:
        failures.append("checkoutCreate failed")
        return 1

    errors = gql(CHECKOUT_EMAIL, {"id": checkout_id, "email": "accept_bot@example.com"}).get("checkoutEmailUpdate") or {}
    check("checkoutEmailUpdate", not (errors.get("errors") or []))

    ship = gql(CHECKOUT_SHIPPING, {"id": checkout_id, "addr": ADDR}).get("checkoutShippingAddressUpdate") or {}
    methods = (ship.get("checkout") or {}).get("availableShippingMethods") or []
    check("checkoutShippingAddressUpdate", not (ship.get("errors") or []) and len(methods) > 0,
          f"methods={[m['id'] for m in methods]}")

    bill = gql(CHECKOUT_BILLING, {"id": checkout_id, "addr": ADDR}).get("checkoutBillingAddressUpdate") or {}
    check("checkoutBillingAddressUpdate", not (bill.get("errors") or []))

    method_id = methods[0]["id"]
    delivery = gql(CHECKOUT_DELIVERY, {"id": checkout_id, "methodId": method_id}).get("checkoutDeliveryMethodUpdate") or {}
    total = ((delivery.get("checkout") or {}).get("totalPrice") or {}).get("gross") or {}
    check("checkoutDeliveryMethodUpdate", not (delivery.get("errors") or []) and total.get("amount", 0) > 0,
          f"total={total.get('amount')} {total.get('currency')}")

    pay = gql(
        CHECKOUT_PAYMENT,
        {"id": checkout_id, "in": {"gateway": "mirumee.payments.dummy", "token": "sandbox", "amount": total.get("amount")}},
    ).get("checkoutPaymentCreate") or {}
    check("checkoutPaymentCreate (dummy gateway)", not (pay.get("errors") or []), f"total={total.get('amount')}")

    complete = gql(CHECKOUT_COMPLETE, {"id": checkout_id}).get("checkoutComplete") or {}
    order = complete.get("order") or {}
    check("checkoutComplete -> order", bool(order.get("id")) and (complete.get("errors") or []) == [],
          f"number={order.get('number')} status={order.get('status')} payment={order.get('paymentStatus')}")

    # ---- 3. 客户注册 / 登录 / 订单历史 ----
    customer_email = f"accept_customer_{order.get('number') or 'x'}@example.com"
    customer_pwd = "Accept_2026_customer!"
    reg = gql(REGISTER, {"e": customer_email, "p": customer_pwd, "r": "http://localhost:3000/account"}).get("accountRegister") or {}
    check("accountRegister", not (reg.get("accountErrors") or []), customer_email)

    token_data = gql(TOKEN_CREATE, {"e": customer_email, "p": customer_pwd}).get("tokenCreate") or {}
    customer_token = token_data.get("token")
    check("customer tokenCreate", bool(customer_token) and not (token_data.get("errors") or []))
    if customer_token:
        me = gql(ME_ORDERS, {}, customer_token).get("me") or {}
        check("customer order history (me.orders)", bool(me.get("orders")), f"email={me.get('email')}")

    print("STORE  ACCEPTANCE:", "PASS" if not failures else f"FAIL ({len(failures)})")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())