import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
ADMIN_EMAIL = os.environ["IAM_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]
CUSTOMER_EMAIL = os.environ["IAM_CUSTOMER_EMAIL"]
CUSTOMER_PASSWORD = os.environ["IAM_CUSTOMER_PASSWORD"]

failures: list[str] = []


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode(errors="replace")}


def check(name: str, condition: bool, detail: str = ""):
    print(("PASS " if condition else "FAIL ") + name + (f" | {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def brief(body) -> str:
    return json.dumps(body, ensure_ascii=False)[:300]


# 1. 未登录访问受保护 API -> 401
status, _ = call("GET", "/iam/me")
check("no token -> 401", status == 401, f"status={status}")

# 2. 非法 token -> 401
status, _ = call("GET", "/iam/me", token="not-a-real-token")
check("invalid token -> 401", status == 401, f"status={status}")

# 3. 参数校验 -> 422
status, _ = call("POST", "/iam/login", {"email": "bad", "password": ""})
check("invalid payload -> 422", status == 422, f"status={status}")

# 4. 管理员登录 -> token
#    注意：不对真实 Saleor 发送"错误密码"。Saleor 有基于 IP 的登录暴力破解保护，
#    错误尝试会暂停该 IP 的全部登录。错误凭据路径由单元测试覆盖：
#    tests/test_iam_api.py::test_login_with_invalid_credentials_returns_401
status, body = call("POST", "/iam/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
check("admin login -> 200", status == 200 and bool(body.get("token")), f"status={status} {brief(body)}")
admin_token = body.get("token", "")

status, me = call("GET", "/iam/me", token=admin_token)
check("admin /me -> 200", status == 200 and me.get("email") == ADMIN_EMAIL, f"status={status}")

# 5. 管理员访问管理员 API -> 200（真实 Saleor 数据）
status, overview = call("GET", "/iam/admin/overview", token=admin_token)
check(
    "admin overview -> 200 with real data",
    status == 200 and "shop_name" in overview and isinstance(overview.get("staff_count"), int),
    f"status={status} shop={overview.get('shop_name')} staff={overview.get('staff_count')} customers={overview.get('customer_count')}",
)

# 6. 普通用户登录
status, body = call("POST", "/iam/login", {"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
check("customer login -> 200", status == 200 and bool(body.get("token")), f"status={status} {brief(body)}")
customer_token = body.get("token", "")

# 7. 普通用户访问管理员 API -> 403
status, _ = call("GET", "/iam/admin/overview", token=customer_token)
check("customer admin overview -> 403", status == 403, f"status={status}")

# 8. 普通用户访问自身信息 -> 200
status, me = call("GET", "/iam/me", token=customer_token)
check("customer /me -> 200", status == 200 and me.get("is_staff") is False, f"status={status}")

print()
print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
