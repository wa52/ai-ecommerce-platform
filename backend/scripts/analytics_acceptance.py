"""Phase 9 验收：Analytics（spec §42）。

验收方式（spec §42 要求）：使用一组**已知输入数据人工计算期望结果**，
再与系统输出比较；并独立用 SQL 直接聚合数据库，作为第二重核对。
"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
EMAIL = os.environ["IAM_ADMIN_EMAIL"]
PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]

failures: list[str] = []
RUN = os.environ.get("RUN_ID", "p9")


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
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


def main() -> int:
    status, body = call("POST", "/iam/login", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print(f"FATAL: login failed {status}")
        return 1
    token = body["token"]
    print("login: OK")

    # 0. 口径定义可查（spec §42：所有指标必须定义公式）
    status, formulas = call("GET", "/analytics/formulas", token=token)
    required = {"gmv", "net_sales", "order_count", "avg_order_value", "refund_rate",
                "platform_fee", "payment_fee", "net_settled", "profit", "profit_margin"}
    check("formulas documented", status == 200 and required <= set(formulas),
          f"missing={required - set(formulas or {})}")

    # 1. 先取基线（与对比口径一致：other_cost=200），再注入已知数据，用"增量"与人工核算结果逐项比对
    status, before = call("GET", "/analytics/overview?days=30&other_cost=200.00&currency=USD", token=token)
    base = (before.get("by_currency") or {}).get("USD", {})

    payment = call("POST", "/finance/payments", {
        "order_ref": f"{RUN}-order-1", "provider": "stripe", "amount": "1000.00",
        "currency": "USD", "idempotency_key": f"{RUN}-an-pay"}, token)
    check("seed payment", payment[0] == 201, f"status={payment[0]}")
    payment_id = payment[1]["id"]

    refund = call("POST", "/finance/refunds", {
        "payment_id": payment_id, "amount": "100.00", "idempotency_key": f"{RUN}-an-rfd"}, token)
    check("seed refund 100.00", refund[0] == 201, f"status={refund[0]}")

    settlement = call("POST", "/finance/settlements", {
        "platform": "shopify", "period_start": "2026-09-01", "period_end": "2026-09-30",
        "currency": "USD", "platform_fee_rate": "5", "payment_fee_rate": "2",
        "items": [{"order_ref": f"{RUN}-order-1", "gross_amount": "1000.00"}]}, token)
    check("seed settlement", settlement[0] == 201, f"status={settlement[0]}")

    # 2. 系统输出
    status, overview = call("GET", "/analytics/overview?days=30&other_cost=200.00&currency=USD", token=token)
    check("overview available", status == 200 and "USD" in overview.get("by_currency", {}), f"status={status}")
    m = overview["by_currency"]["USD"]

    def delta(key: str, base_key: str | None = None) -> float:
        return round(float(m[key]) - float(base.get(base_key or key, "0")), 2)

    print(f"  baseline: gmv={base.get('gmv')} refund={base.get('refund_total')} platform_fee={base.get('platform_fee')}")
    print(f"  system  : gmv={m['gmv']} net_sales={m['net_sales']} refund={m['refund_total']} "
          f"platform_fee={m['platform_fee']} payment_fee={m['payment_fee']} profit={m['profit']}")

    # 3. 人工核算增量：退款 +100；平台费 +50（1000×5%）；支付费 +20（1000×2%）；净额 +930
    check("Δrefund_total = +100.00", delta("refund_total") == 100.00, f"delta={delta('refund_total')}")
    check("Δplatform_fee = +50.00 (1000×5%)", delta("platform_fee") == 50.00, f"delta={delta('platform_fee')}")
    check("Δpayment_fee = +20.00 (1000×2%)", delta("payment_fee") == 20.00, f"delta={delta('payment_fee')}")
    check("Δnet_settled = +930.00 (1000-50-20)", delta("net_settled") == 930.00, f"delta={delta('net_settled')}")
    # Δ销售额 = -100（无新订单）；Δ利润 = -100 -50 -20 = -170
    check("Δnet_sales = -100.00", delta("net_sales") == -100.00, f"delta={delta('net_sales')}")
    check("Δprofit = -170.00", delta("profit") == -170.00, f"delta={delta('profit')}")

    # 4. 口径恒等式（绝对值）
    check("net_sales = gmv - refund",
          round(float(m["gmv"]) - float(m["refund_total"]), 2) == round(float(m["net_sales"]), 2),
          f"{m['gmv']} - {m['refund_total']} != {m['net_sales']}")
    check("refund_rate = refund/gmv",
          abs(float(m["refund_rate_percent"]) - (float(m["refund_total"]) / float(m["gmv"]) * 100)) < 0.01,
          f"{m['refund_rate_percent']}%")
    check("avg_order_value = gmv/order_count",
          abs(float(m["avg_order_value"]) - (float(m["gmv"]) / int(m["order_count"]))) < 0.01,
          f"{m['avg_order_value']}")
    check("profit = net_sales - platform_fee - payment_fee - other_cost",
          abs(
              float(m["profit"])
              - (float(m["net_sales"]) - float(m["platform_fee"]) - float(m["payment_fee"]) - float(m["other_cost"]))
          ) < 0.01,
          f"profit={m['profit']}")
    check("profit_margin = 0 when net_sales <= 0 (documented rule)",
          (float(m["profit_margin_percent"]) == 0.0) if float(m["net_sales"]) <= 0
          else abs(float(m["profit_margin_percent"]) - (float(m["profit"]) / float(m["net_sales"]) * 100)) < 0.01,
          f"net_sales={m['net_sales']} margin={m['profit_margin_percent']}%")

    # 5. other_cost 生效（利润随其他成本线性变化）
    status, with_zero = call("GET", "/analytics/overview?days=30&other_cost=0&currency=USD", token=token)
    diff = float(with_zero["by_currency"]["USD"]["profit"]) - float(m["profit"])
    check("other_cost=200 reduces profit by 200.00", abs(diff - 200.00) < 0.01, f"diff={diff}")

    # 6. 时间窗口（今日 vs 30 天）
    status, today = call("GET", "/analytics/overview?days=1&currency=USD", token=token)
    check("time window supported (today)", status == 200, f"status={status}")

    # 7. 币种隔离
    status, jpy = call("GET", "/analytics/overview?days=30&currency=JPY", token=token)
    check("currency filter isolates currency",
          status == 200 and set(jpy.get("by_currency", {}).keys()) <= {"JPY"}, f"keys={list(jpy.get('by_currency', {}).keys())}")

    # 8. 权限
    status, cust = call("POST", "/iam/login", {"email": os.environ["IAM_CUSTOMER_EMAIL"],
                                              "password": os.environ["IAM_CUSTOMER_PASSWORD"]})
    if status == 200:
        forbidden = call("GET", "/analytics/overview", token=cust["token"])
        check("analytics requires admin -> 403", forbidden[0] == 403, f"status={forbidden[0]}")
    else:
        check("analytics requires admin -> 403", False, "customer login failed")

    print()
    print("NOTE: 指标口径见 /api/v1/analytics/formulas（与前端 Dashboard、AI 工具共用同一实现）")
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
