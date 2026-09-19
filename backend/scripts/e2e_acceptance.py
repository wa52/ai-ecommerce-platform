"""最终端到端验收（spec §52）：完整业务闭环。

链路：
  登录 → 创建店铺（凭据加密）→ 平台授权（Sandbox Shopify）→ 同步商品
  → 库存更新 → Payment/Refund/Settlement → Finance
  → Analytics Dashboard 指标 → Agent 查询真实业务数据 → RAG 查询知识库 → 返回前端可用结果

前置（Sandbox）：
  - 本脚本启动 Fake Shopify（默认 9099）与 Fake LLM（默认 9098）
  - ai-backend 需配置：
      SHOPIFY_SHOP_DOMAIN=host.docker.internal:9099
      SHOPIFY_ACCESS_TOKEN=fake-token
      SHOPIFY_API_SCHEME=http
      LLM_BASE_URL=http://host.docker.internal:9098/v1
      LLM_API_KEY=sk-sandbox-key
"""

import hashlib
import hmac
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
CUSTOMER_EMAIL = os.environ["IAM_CUSTOMER_EMAIL"]
CUSTOMER_PASSWORD = os.environ["IAM_CUSTOMER_PASSWORD"]
WEBHOOK_SECRET = os.environ["PAYMENT_WEBHOOK_SECRET"]
SHOPIFY_PORT = int(os.environ.get("FAKE_SHOPIFY_PORT", "9099"))
LLM_PORT = int(os.environ.get("FAKE_LLM_PORT", "9098"))
LLM_KEY = os.environ.get("LLM_API_KEY", "sk-sandbox-key")
RUN = os.environ.get("RUN_ID", "e2e")

failures: list[str] = []
steps: list[str] = []
state: dict = {"kb_id": None}


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"{status} {name}" + (f" | {detail}" if detail else ""))
    steps.append(f"{status} {name}")
    if not condition:
        failures.append(name)


# ---------------- Fake Shopify ----------------

def shopify_response(query: str) -> dict:
    if "products" in query:
        return {
            "data": {
                "products": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/Product/9001",
                                "title": "E2E Sandbox Mug",
                                "description": "sandbox",
                                "variants": {"edges": [{"node": {"sku": "E2E-MUG-1", "price": "12.00", "inventoryQuantity": 6}}]},
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
                                "id": "gid://shopify/Order/7001",
                                "name": "#7001",
                                "displayFulfillmentStatus": "UNFULFILLED",
                                "displayFinancialStatus": "PAID",
                                "createdAt": "2026-09-19T12:00:00Z",
                                "currencyCode": "USD",
                                "currentTotalPriceSet": {"shopMoney": {"amount": "24.00", "currencyCode": "USD"}},
                                "lineItems": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": "gid://shopify/LineItem/1",
                                                "title": "E2E Sandbox Mug",
                                                "sku": "E2E-MUG-1",
                                                "quantity": 2,
                                                "originalUnitPriceSet": {"shopMoney": {"amount": "12.00", "currencyCode": "USD"}},
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
    if "shop" in query:
        return {"data": {"shop": {"name": "E2E Sandbox Shop", "myshopifyDomain": "e2e.myshopify.com"}}}
    return {"errors": [{"message": "unsupported"}]}


class ShopifyHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.headers.get("X-Shopify-Access-Token") != "fake-token":
            self._send(401, {"errors": "Invalid API key"})
            return
        self._send(200, shopify_response(body.get("query", "")))

    def _send(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


# ---------------- Fake LLM ----------------

class LlmHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.headers.get("Authorization") != f"Bearer {LLM_KEY}":
            self._send(401, {"error": {"message": "invalid api key"}})
            return

        messages = body.get("messages", [])
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        user_text = " ".join(m.get("content") or "" for m in messages if m.get("role") == "user")

        if tool_messages:
            payload = json.loads(tool_messages[-1].get("content") or "{}")
            data = payload.get("data") or {}
            if data.get("note"):
                answer = f"没有可用数据：{data['note']}"
            elif "by_currency" in data:
                answer = "依据真实订单数据：" + "；".join(
                    f"{cur} 订单 {v['orders']} 笔，销售额 {v['gross']}" for cur, v in data["by_currency"].items()
                )
            elif "chunks" in data:
                first = (data["chunks"] or [{}])[0]
                answer = f"依据知识库 [1]（{first.get('document_title')}）：{str(first.get('content'))[:60]}"
            else:
                answer = f"工具返回：{json.dumps(data, ensure_ascii=False)[:200]}"
            self._send(200, self._chat(answer))
            return

        if body.get("tools"):
            if "知识库" in user_text:
                call = {"id": "c1", "type": "function", "function": {"name": "rag.search", "arguments": json.dumps({"knowledge_base_id": state["kb_id"], "query": "退货窗口", "top_k": 2})}}
            elif "订单" in user_text:
                call = {"id": "c1", "type": "function", "function": {"name": "commerce.recent_orders", "arguments": '{"limit": 5}'}}
            else:
                call = {"id": "c1", "type": "function", "function": {"name": "analytics.sales_summary", "arguments": '{"limit": 20}'}}
            self._send(200, {
                "model": "fake-model",
                "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [call]}, "finish_reason": "tool_calls"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            })
            return

        # 文案 / 翻译 / RAG answer
        if "翻译" in user_text:
            content = json.dumps({"title": "E2E English Title", "description": "EN desc", "bullets": ["b1"]}, ensure_ascii=False)
        elif "文案" in user_text or "卖点" in user_text or "商品名称" in user_text:
            content = json.dumps({"title": "E2E 标题", "bullets": ["卖点一"], "description": "描述"}, ensure_ascii=False)
        else:
            content = "依据资料 [1]：标准退货窗口为 30 天。"
        self._send(200, self._chat(content))

    @staticmethod
    def _chat(content: str) -> dict:
        return {
            "model": "fake-model",
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 6, "total_tokens": 14},
        }

    def _send(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def call(method: str, path: str, body: dict | None = None, token: str | None = None, raw: bytes | None = None,
         headers: dict | None = None):
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(f"{API}{path}", data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 204:
                return 204, {}
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload)
        except json.JSONDecodeError:
            return exc.code, {"raw": payload.decode(errors="replace")}


def main() -> int:
    threading.Thread(
        target=HTTPServer(("0.0.0.0", SHOPIFY_PORT), ShopifyHandler).serve_forever, daemon=True
    ).start()
    threading.Thread(
        target=HTTPServer(("0.0.0.0", LLM_PORT), LlmHandler).serve_forever, daemon=True
    ).start()
    print(f"sandbox: shopify :{SHOPIFY_PORT}, llm :{LLM_PORT}")

    # 1. 登录
    status, body = call("POST", "/iam/login", {"email": EMAIL, "password": PASSWORD})
    check("1. 用户登录", status == 200 and bool(body.get("token")), f"status={status}")
    token = body.get("token", "")

    # 2. 创建/连接店铺（凭据加密）
    status, store = call("POST", "/stores", {
        "name": "E2E Shopify Store", "platform": "shopify", "currency": "USD", "country": "US",
        "credentials": {"access_token": "fake-token", "shop_domain": f"host.docker.internal:{SHOPIFY_PORT}"},
    }, token)
    if status == 201:
        check("2. 创建店铺（凭据加密）", True, f"masked={store['credentials_masked']}")
    else:
        check("2. 创建店铺（凭据加密）", False, f"status={status}")

    # 3. 平台授权（Sandbox Shopify 健康检查）
    status, health = call("GET", "/connectors/shopify/health", token=token)
    check("3. 平台授权（Shopify 连接）", status == 200 and health.get("ok") is True,
          f"status={status} detail={str(health.get('detail'))[:60]}")

    # 4. 同步商品
    status, sync = call("POST", "/connectors/shopify/sync/products?limit=10", token=token)
    ok_sync = status == 200 and (sync.get("created", 0) + sync.get("reused", 0)) >= 1
    check("4. 同步商品（平台 → Saleor）", ok_sync, f"status={status} result={sync if status == 200 else sync}")

    # 5. 同步订单（通过 Agent 的订单工具读取真实订单）
    status, orders = call("GET", "/commerce/orders?first=5", token=token)
    check("5. 订单读取（含平台同步订单）", status == 200 and orders["page"]["total_count"] >= 1,
          f"total={orders['page']['total_count'] if status == 200 else '?'}")

    # 6. 库存更新
    status, inv = call("GET", "/commerce/inventory?first=100", token=token)
    rows = inv.get("items", []) if status == 200 else []
    if rows:
        variant_id = rows[0]["variant_id"]
        warehouse_id = rows[0].get("warehouse_id")
        warehouses = call("GET", "/commerce/warehouses", token=token)[1]
        warehouse_id = warehouse_id or (warehouses[0]["id"] if warehouses else None)
        status, updated = call("POST", "/commerce/inventory",
                               {"variant_id": variant_id, "warehouse_id": warehouse_id, "quantity": 9}, token)
        check("6. 库存更新", status == 200 and updated[0]["quantity"] == 9,
              f"status={status} qty={updated[0]['quantity'] if status == 200 else '?'}")
    else:
        check("6. 库存更新", False, "没有可用 SKU")

    # 7. Payment / Refund / Settlement
    status, payment = call("POST", "/finance/payments", {
        "order_ref": f"{RUN}-order-1", "provider": "stripe", "amount": "24.00",
        "currency": "USD", "idempotency_key": f"{RUN}-pay"}, token)
    check("7a. Payment", status == 201, f"status={status}")
    payment_id = payment["id"] if status == 201 else None

    status, refund = call("POST", "/finance/refunds", {
        "payment_id": payment_id, "amount": "4.00", "idempotency_key": f"{RUN}-rfd"}, token)
    check("7b. Refund（部分退款）", status == 201, f"status={status}")

    status, settlement = call("POST", "/finance/settlements", {
        "platform": "shopify", "period_start": "2026-09-01", "period_end": "2026-09-30",
        "currency": "USD", "platform_fee_rate": "5", "payment_fee_rate": "2",
        "items": [{"order_ref": f"{RUN}-order-1", "gross_amount": "24.00"}]}, token)
    check("7c. Settlement", status == 201 and settlement["net_amount"] == "22.32",
          f"net={settlement.get('net_amount') if status == 201 else status}")

    # 7d. Webhook 验签 + 幂等
    event = {"id": f"{RUN}-evt", "order_ref": f"{RUN}-order-1", "amount": "24.00", "currency": "USD"}
    raw = json.dumps(event).encode()
    sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    bad = call("POST", "/finance/webhooks/stripe", raw=raw, headers={"X-Signature": "sha256=bad"})
    good = call("POST", "/finance/webhooks/stripe", raw=raw, headers={"X-Signature": sig})
    dup = call("POST", "/finance/webhooks/stripe", raw=raw, headers={"X-Signature": sig})
    check("7d. Webhook 验签 + 重复投递幂等",
          bad[0] == 401 and good[1].get("duplicate") is False and dup[1].get("duplicate") is True,
          f"bad={bad[0]} dup={dup[1].get('duplicate')}")

    # 8. Finance / Analytics 指标
    status, ledger = call("GET", "/finance/ledger?limit=50", token=token)
    check("8a. Finance 流水可追溯", status == 200 and len(ledger) >= 3, f"entries={len(ledger) if status == 200 else '?'}")

    status, overview = call("GET", "/analytics/overview?days=30&other_cost=0&currency=USD", token=token)
    metrics = (overview.get("by_currency") or {}).get("USD", {}) if status == 200 else {}
    check("8b. Analytics 指标（Dashboard 数据源）",
          status == 200 and bool(metrics.get("gmv")) and bool(metrics.get("profit") is not None),
          f"gmv={metrics.get('gmv')} profit={metrics.get('profit')}")

    # 9. AI 文案 / 翻译
    status, copy = call("POST", "/ai/copy/product", {"product_name": "E2E Sandbox Mug", "language": "英文"}, token)
    check("9a. AI 商品文案", status == 200 and bool(copy.get("title")), f"status={status}")
    status, translated = call("POST", "/ai/translate",
                              {"title": "E2E 标题", "description": "描述", "bullets": ["卖点"], "target_language": "英语"}, token)
    check("9b. AI 翻译", status == 200 and bool(translated.get("title")), f"status={status}")

    # 10. RAG 知识库
    slug = f"{RUN}-kb"
    status, kb = call("POST", "/rag/knowledge-bases", {"name": "E2E 知识库", "slug": slug}, token)
    if status == 409:
        kb = next(k for k in call("GET", "/rag/knowledge-bases", token=token)[1] if k["slug"] == slug)
    state["kb_id"] = kb["id"]
    call("POST", f"/rag/knowledge-bases/{kb['id']}/documents",
         {"title": "退货政策", "content": "标准退货窗口为 30 天。", "source": "returns.md"}, token)
    status, answer = call("POST", f"/rag/knowledge-bases/{kb['id']}/answer", {"query": "退货窗口是多久"}, token)
    check("10. RAG 知识库检索 + 引用回答",
          status == 200 and answer.get("grounded") is True and bool(answer.get("contexts")),
          f"grounded={answer.get('grounded')} contexts={len(answer.get('contexts') or [])}")

    # 11. Agent 查询真实业务数据
    status, run = call("POST", "/agent/run", {"agent": "operations", "prompt": "查询最近 30 天销售情况"}, token)
    inv = (run.get("tool_invocations") or [{}])[0]
    check("11. Agent 查询真实业务数据",
          status == 200 and inv.get("name") == "analytics.sales_summary" and inv.get("ok") is True
          and bool((inv.get("result") or {}).get("by_currency")),
          f"tool={inv.get('name')} sampled={(inv.get('result') or {}).get('sampled_orders')}")

    # 12. Agent 使用 RAG
    status, rag_run = call("POST", "/agent/run", {"agent": "operations", "prompt": "根据知识库说明退货政策"}, token)
    rag_inv = (rag_run.get("tool_invocations") or [{}])[0]
    check("12. Agent 调用 RAG 能力", rag_inv.get("name") == "rag.search" and rag_inv.get("ok") is True,
          f"tool={rag_inv.get('name')}")

    # 13. 前端可用性（HTTP 可达）
    try:
        with urllib.request.urlopen(os.environ.get("FRONTEND_URL", "http://localhost:3000"), timeout=20) as resp:
            check("13. 前端可达（结果可返回前端）", resp.status == 200, f"status={resp.status}")
    except Exception as exc:  # noqa: BLE001
        check("13. 前端可达（结果可返回前端）", False, f"{type(exc).__name__}")

    # 14. 权限约束贯穿
    status, cust = call("POST", "/iam/login", {"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    if status == 200:
        denied = call("GET", "/finance/payments", token=cust["token"])[0]
        denied2 = call("GET", "/analytics/overview", token=cust["token"])[0]
        check("14. 权限约束（普通用户受限）", denied == 403 and denied2 == 403, f"finance={denied} analytics={denied2}")
    else:
        check("14. 权限约束（普通用户受限）", False, "customer login failed")

    print()
    print(f"STEPS: {len(steps)}")
    print("REAL_INTEGRATION: NOT_VERIFIED (Shopify 与 LLM 均为 Sandbox)")
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
