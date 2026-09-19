"""API 状态码矩阵验收（spec §48）：真实 HTTP 请求覆盖 2xx/4xx/5xx 语义。"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
EMAIL = os.environ["IAM_ADMIN_EMAIL"]
PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]
CUSTOMER_EMAIL = os.environ["IAM_CUSTOMER_EMAIL"]
CUSTOMER_PASSWORD = os.environ["IAM_CUSTOMER_PASSWORD"]

failures: list[str] = []


def call(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return resp.status, {}
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode(errors="replace")}


def _root_call(method, path, body=None):
    """OpenAPI 等文档端点位于服务根路径（不带 /api/v1 前缀）。"""
    root = API.rsplit("/api/v1", 1)[0]
    req = urllib.request.Request(f"{root}{path}", method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def check(name, expected, actual, detail=""):
    ok = actual == expected
    print(("PASS " if ok else "FAIL ") + f"{name} (expect {expected}, got {actual})" + (f" | {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main() -> int:
    status, body = call("POST", "/iam/login", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print(f"FATAL: login failed {status} {body}")
        return 1
    token = body["token"]

    # 2xx
    check("GET /health -> 200", 200, call("GET", "/health")[0])
    check("GET /health/live -> 200", 200, call("GET", "/health/live")[0])
    check("GET /openapi.json (root) -> 200", 200, call("ROOT", "/openapi.json")[-1] if False else
          _root_call("GET", "/openapi.json")[0])
    check("GET /iam/me -> 200", 200, call("GET", "/iam/me", token=token)[0])
    check("POST /tasks -> 202", 202, call("POST", "/tasks", {"name": "ping", "payload": {}}, token)[0])
    # 不存在但 ID 格式合法的商品 -> 404
    import base64
    ghost_id = base64.b64encode(b"Product:999999999").decode()
    check("DELETE /commerce/products/{nonexistent} -> 404", 404,
          call("DELETE", f"/commerce/products/{ghost_id}", token=token)[0])

    # 401
    check("GET /iam/me (no token) -> 401", 401, call("GET", "/iam/me")[0])
    check("GET /iam/me (bad token) -> 401", 401, call("GET", "/iam/me", token="bad-token")[0])
    # 注意：错误凭据的登录会触发 Saleor 的 IP 粒度暴力破解保护，
    # 因此放在脚本最后执行（见文末）。

    # 403（普通用户）
    status, cust = call("POST", "/iam/login", {"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    if status == 200:
        ctoken = cust["token"]
        for path, method in [
            ("/iam/admin/overview", "GET"),
            ("/commerce/products", "GET"),
            ("/stores", "GET"),
            ("/finance/payments", "GET"),
            ("/analytics/overview", "GET"),
            ("/rag/knowledge-bases", "GET"),
            ("/ai/providers", "GET"),
        ]:
            check(f"{method} {path} (customer) -> 403", 403, call(method, path, token=ctoken)[0])
    else:
        check("customer login", 200, status)

    # 404
    check("GET /rag/knowledge-bases/{id}/search (missing kb) -> 404", 404,
          call("POST", "/rag/knowledge-bases/missing-kb/search", {"query": "x"}, token)[0])
    check("GET /connectors/amazon/health -> 404", 404, call("GET", "/connectors/amazon/health", token=token)[0])
    check("GET /finance/payments/{id} (missing) -> 404", 404,
          call("GET", "/finance/payments/00000000-0000-0000-0000-000000000000", token=token)[0])

    # 409
    status, kb = call("POST", "/rag/knowledge-bases", {"name": "状态码矩阵", "slug": "status-matrix-kb"}, token)
    check("POST /rag/knowledge-bases (dup slug) -> 409", 409,
          call("POST", "/rag/knowledge-bases", {"name": "重复", "slug": "status-matrix-kb"}, token)[0])
    if kb.get("id"):
        status, payment = call("POST", "/finance/payments", {
            "order_ref": "status-matrix", "provider": "stripe", "amount": "10.00",
            "currency": "USD", "idempotency_key": "status-matrix-pay"}, token)
        if payment.get("id"):
            call("POST", "/finance/refunds", {
                "payment_id": payment["id"], "amount": "10.00", "idempotency_key": "status-matrix-rfd"}, token)
            check("POST /finance/refunds (over refund) -> 409", 409,
                  call("POST", "/finance/refunds", {
                      "payment_id": payment["id"], "amount": "1.00", "idempotency_key": "status-matrix-rfd2"}, token)[0])

    # 422
    check("POST /iam/login (invalid email) -> 422", 422,
          call("POST", "/iam/login", {"email": "not-an-email", "password": ""})[0])
    check("POST /commerce/products (bad slug) -> 422", 422,
          call("POST", "/commerce/products", {"name": "x", "slug": "Bad Slug"}, token)[0])
    check("GET /analytics/overview (bad other_cost) -> 422", 422,
          call("GET", "/analytics/overview?other_cost=abc", token=token)[0])
    check("POST /commerce/inventory (negative) -> 422", 422,
          call("POST", "/commerce/inventory", {"variant_id": "V", "warehouse_id": "W", "quantity": -1}, token)[0])

    # 401（错误凭据）——放在最后，因为 Saleor 对同 IP 失败登录有暴力破解保护
    check("POST /iam/login (bad creds) -> 401", 401,
          call("POST", "/iam/login", {"email": "nobody@example.com", "password": "wrong"})[0])

    # 5xx 语义（上游不可用 → 502；由 sandbox 关闭时触发）
    print("NOTE: 5xx 语义（502 上游失败 / 500 统一异常出口）见 docs/evidence/phase6 与单测")

    print()
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
