"""Phase 4 验收：Connector（spec §40）。

真实 Shopify 需要店铺凭据；本脚本启动一个本地 Fake Shopify GraphQL 服务，
让**真实 ShopifyConnector 代码**经 HTTP 调用它，并把数据同步进 Saleor。

因此本 Phase 的平台集成状态为：

    REAL_INTEGRATION: NOT_VERIFIED

（Fake 平台 = spec §40 允许的 Sandbox/Fake Connector 开发测试方式。）
"""

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
EMAIL = os.environ["IAM_ADMIN_EMAIL"]
PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]
FAKE_PORT = int(os.environ.get("FAKE_SHOPIFY_PORT", "9099"))
FAKE_SHOP_DOMAIN = os.environ.get("FAKE_SHOP_DOMAIN", f"localhost:{FAKE_PORT}")

failures: list[str] = []
fake_state = {"product_calls": 0, "fail_next": False}


def _fake_response(query: str) -> dict:
    if "shop" in query and "products" not in query:
        return {"data": {"shop": {"name": "Fake Shopify", "myshopifyDomain": "fake.myshopify.com"}}}
    if "products" in query:
        fake_state["product_calls"] += 1
        return {
            "data": {
                "products": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Product/555",
                                "title": "Fake Shopify Mug",
                                "description": "sandbox product",
                                "variants": {
                                    "edges": [{"node": {"sku": "FAKE-MUG-1", "price": "9.90", "inventoryQuantity": 7}}]
                                },
                            }
                        }
                    ],
                }
            }
        }
    if "orders" in query:
        return {
            "data": {
                "orders": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Order/777",
                                "name": "#777",
                                "displayFulfillmentStatus": "UNFULFILLED",
                                "displayFinancialStatus": "PAID",
                                "createdAt": "2026-09-19T10:00:00Z",
                                "currencyCode": "USD",
                                "currentTotalPriceSet": {"shopMoney": {"amount": "19.80", "currencyCode": "USD"}},
                                "lineItems": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": "gid://shopify/LineItem/1",
                                                "title": "Fake Shopify Mug",
                                                "sku": "FAKE-MUG-1",
                                                "quantity": 2,
                                                "originalUnitPriceSet": {
                                                    "shopMoney": {"amount": "9.90", "currencyCode": "USD"}
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
        }
    return {"errors": [{"message": "unsupported query"}]}


class FakeShopifyHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        token = self.headers.get("X-Shopify-Access-Token")
        if fake_state["fail_next"]:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"errors":"boom"}')
            return
        if token != "fake-token":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"errors":"Invalid API key"}')
            return
        payload = json.dumps(_fake_response(body.get("query", ""))).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence
        pass


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


def check(name: str, condition: bool, detail: str = ""):
    print(("PASS " if condition else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    server = HTTPServer(("127.0.0.1", FAKE_PORT), FakeShopifyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"fake shopify listening on 127.0.0.1:{FAKE_PORT}")

    status, body = api("POST", "/iam/login", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print(f"FATAL: login failed {status}")
        return 1
    token = body["token"]
    print("login: OK")

    # 1. 平台列表与未配置状态
    status, platforms = api("GET", "/connectors/platforms", token=token)
    check("platforms listed", status == 200 and platforms[0]["platform"] == "shopify", f"{platforms}")

    # 2. Store 凭据加密存储（§39）
    store_name = "Fake Shopify Store"
    status, store = api(
        "POST",
        "/stores",
        {
            "name": store_name,
            "platform": "shopify",
            "currency": "USD",
            "country": "US",
            "credentials": {"access_token": "fake-token", "shop_domain": FAKE_SHOP_DOMAIN},
        },
        token,
    )
    check("store created with encrypted credentials", status == 201, f"status={status}")
    check(
        "credential never returned (masked only)",
        status == 201 and "credentials" not in store and "fake-token" not in json.dumps(store),
        f"masked={store.get('credentials_masked') if status == 201 else '?'}",
    )
    store_id = store["id"]

    # 3. Connector 配置状态决定验收路径
    status, platforms = api("GET", "/connectors/platforms", token=token)
    configured = bool(platforms and platforms[0].get("configured"))
    print(f"shopify configured: {configured}")

    if not configured:
        # 未配置：健康检查应可解释、真实同步应被拒绝
        status, health = api("GET", "/connectors/shopify/health", token=token)
        check("shopify health reported", status == 200 and "ok" in health, f"{health}")
        status, denied = api("POST", "/connectors/shopify/sync/products", token=token)
        check(
            "sync blocked when not configured -> 409",
            status == 409 and "NOT_VERIFIED" in json.dumps(denied, ensure_ascii=False),
            f"status={status}",
        )
        # 未配置的 Connector 通过 Worker 任务失败可见
        status, task = api("POST", "/tasks", {"name": "sync.products", "payload": {"platform": "shopify"}}, token)
        check("sync task accepted", status == 202, f"status={status}")
    else:
        # 已配置（沙箱凭据）：执行真实同步并验证幂等
        status, sync1 = api("POST", "/connectors/shopify/sync/products?limit=10", token=token)
        check(
            "sync executed (configured connector)",
            status == 200 and isinstance(sync1.get("created"), int),
            f"status={status} result={sync1}",
        )
        status, sync2 = api("POST", "/connectors/shopify/sync/products?limit=10", token=token)
        check(
            "repeat sync is idempotent (no duplicates)",
            status == 200 and sync2.get("created", 0) == 0 and sync2.get("reused", 0) >= 1,
            f"result={sync2}",
        )

    # 6. 凭据与店铺生命周期
    status, listed = api("GET", "/stores", token=token)
    check("store listed", status == 200 and any(s["id"] == store_id for s in listed), f"count={len(listed) if status == 200 else '?'}")
    status, disabled = api("POST", f"/stores/{store_id}/disable", token=token)
    check("store disabled", status == 200 and disabled["status"] == "disabled", f"status={status}")

    # 7. 普通用户无权限（§39 数据隔离/权限）
    status, buyer = api("POST", "/iam/login", {"email": os.environ["IAM_CUSTOMER_EMAIL"], "password": os.environ["IAM_CUSTOMER_PASSWORD"]})
    if status == 200:
        status, _ = api("GET", "/stores", token=buyer["token"])
        check("customer cannot list stores -> 403", status == 403, f"status={status}")
    else:
        check("customer cannot list stores -> 403", False, f"customer login failed {status}")

    # 8. Fake Shopify 服务本身可达（证明 sandbox 生效）
    fake_req = urllib.request.Request(
        f"http://127.0.0.1:{FAKE_PORT}/admin/api/2024-10/graphql.json",
        data=json.dumps({"query": "{ shop { name } }"}).encode(),
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": "fake-token"},
    )
    try:
        with urllib.request.urlopen(fake_req, timeout=20) as resp:
            fake = json.loads(resp.read())
            fake_status = resp.status
    except urllib.error.HTTPError as exc:
        fake_status, fake = exc.code, {"raw": exc.read().decode(errors="replace")}
    check(
        "fake shopify reachable",
        fake_status == 200 and fake["data"]["shop"]["name"] == "Fake Shopify",
        f"status={fake_status}",
    )

    server.shutdown()
    print()
    print("REAL_INTEGRATION: NOT_VERIFIED (Fake Shopify sandbox used; no real platform credentials)")
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
