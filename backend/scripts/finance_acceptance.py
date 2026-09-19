"""Phase 5 验收：Finance（spec §41）。真实 PostgreSQL + 真实 HTTP API。"""

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
EMAIL = os.environ["IAM_ADMIN_EMAIL"]
PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]
WEBHOOK_SECRET = os.environ["PAYMENT_WEBHOOK_SECRET"]

failures: list[str] = []
run = os.environ.get("RUN_ID", "p5")


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
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, (json.loads(resp.read()) if resp.status != 204 else {})
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload)
        except json.JSONDecodeError:
            return exc.code, {"raw": payload.decode(errors="replace")}


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

    # 1. 正常支付 + 幂等（同一 Idempotency Key 重复 N 次只产生一次有效交易）
    key = f"{run}-pay-1"
    payload = {"order_ref": f"{run}-order-1", "provider": "stripe", "amount": "100.00",
               "currency": "USD", "idempotency_key": key}
    first = call("POST", "/finance/payments", payload, token)
    check("payment created -> 201", first[0] == 201 and first[1]["created"] is True, f"status={first[0]}")
    payment_id = first[1]["id"]
    for _ in range(3):
        repeat = call("POST", "/finance/payments", payload, token)
        if repeat[1]["id"] != payment_id or repeat[1]["created"] is not False:
            check("idempotent payment", False, f"{repeat[1]}")
            break
    else:
        check("idempotent payment (4x same key -> 1 txn)", True, f"payment_id={payment_id}")

    # 2. 金额精度（Decimal，按币种 2 位）
    check("decimal amount formatted by currency", first[1]["amount"] == "100.00", f"amount={first[1]['amount']}")

    # 3. 支付失败路径（金额非法/为零）
    bad = call("POST", "/finance/payments", {**payload, "idempotency_key": f"{run}-pay-bad", "amount": "0.00"}, token)
    check("zero amount rejected -> 422", bad[0] == 422, f"status={bad[0]}")

    # 4. 部分退款 / 重复退款 / 超额退款
    r1 = call("POST", "/finance/refunds", {"payment_id": payment_id, "amount": "30.00",
                                          "idempotency_key": f"{run}-rfd-1", "reason": "部分退款"}, token)
    check("partial refund -> 201", r1[0] == 201 and r1[1]["amount"] == "30.00", f"status={r1[0]} {r1[1].get('amount')}")
    dup = call("POST", "/finance/refunds", {"payment_id": payment_id, "amount": "30.00",
                                           "idempotency_key": f"{run}-rfd-1"}, token)
    check("duplicate refund is idempotent", dup[1]["created"] is False, f"created={dup[1].get('created')}")
    over = call("POST", "/finance/refunds", {"payment_id": payment_id, "amount": "80.00",
                                            "idempotency_key": f"{run}-rfd-2"}, token)
    check("over refund rejected -> 409", over[0] == 409, f"status={over[0]}")

    # 5. 全额退款（补齐剩余）
    full = call("POST", "/finance/refunds", {"payment_id": payment_id, "amount": "70.00",
                                            "idempotency_key": f"{run}-rfd-3"}, token)
    check("full refund completes payment", full[0] == 201, f"status={full[0]}")
    after = call("GET", f"/finance/payments/{payment_id}", token=token)
    check("refunded_amount tracks cumulative refunds", after[1]["refunded_amount"] == "100.00",
          f"refunded={after[1]['refunded_amount']}")

    # 6. Webhook 验签 + 重复投递
    event = {"id": f"{run}-evt-1", "order_ref": f"{run}-order-2", "amount": "19.80", "currency": "USD"}
    raw = json.dumps(event).encode()
    sig = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    invalid = call("POST", "/finance/webhooks/stripe", raw=raw, headers={"X-Signature": "sha256=bad"})
    check("invalid webhook signature -> 401", invalid[0] == 401, f"status={invalid[0]}")
    ok = call("POST", "/finance/webhooks/stripe", raw=raw, headers={"X-Signature": sig})
    check("valid webhook processed", ok[0] == 200 and ok[1]["duplicate"] is False, f"status={ok[0]}")
    again = call("POST", "/finance/webhooks/stripe", raw=raw, headers={"X-Signature": sig})
    check("duplicate webhook no double effect", again[0] == 200 and again[1]["duplicate"] is True,
          f"duplicate={again[1].get('duplicate')}")

    # 7. 结算（平台手续费 + 支付手续费 + 净额）
    settlement = call("POST", "/finance/settlements", {
        "platform": "shopify",
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "currency": "USD",
        "platform_fee_rate": "5",
        "payment_fee_rate": "2",
        "items": [{"order_ref": f"{run}-order-1", "gross_amount": "1000.00"},
                  {"order_ref": f"{run}-order-2", "gross_amount": "500.00"}],
    }, token)
    s = settlement[1]
    check("settlement computed (gross/fees/net)",
          settlement[0] == 201 and s["gross_amount"] == "1500.00" and s["platform_fee"] == "75.00"
          and s["payment_fee"] == "30.00" and s["net_amount"] == "1395.00",
          f"{s.get('gross_amount')}/{s.get('platform_fee')}/{s.get('payment_fee')}/{s.get('net_amount')}")

    # 8. 对账（一致 / 差异）
    matched = call("POST", "/finance/reconciliations", {"settlement_id": s["id"], "actual_net": "1395.00"}, token)
    check("reconciliation matched", matched[1]["status"] == "matched", f"{matched[1].get('status')}")
    mismatch = call("POST", "/finance/reconciliations",
                    {"settlement_id": s["id"], "actual_net": "1390.00", "note": "差异"}, token)
    check("reconciliation mismatch detected", mismatch[1]["status"] == "mismatched"
          and mismatch[1]["difference"] == "-5.00", f"diff={mismatch[1].get('difference')}")

    # 9. 多币种
    jpy = call("POST", "/finance/payments", {"order_ref": f"{run}-order-jpy", "provider": "stripe",
                                            "amount": "1000", "currency": "JPY",
                                            "idempotency_key": f"{run}-pay-jpy"}, token)
    check("multi-currency payment (JPY 0 decimals)", jpy[0] == 201 and jpy[1]["amount"] == "1000",
          f"amount={jpy[1].get('amount')}")

    # 10. 可追溯：Ledger 有记录
    ledger = call("GET", "/finance/ledger?limit=200", token=token)
    types = {e["entry_type"] for e in ledger[1]}
    check("ledger records payment/refund/settlement", {"payment", "refund", "settlement"} <= types, f"types={types}")

    # 11. 权限
    buyer = call("POST", "/iam/login", {"email": os.environ["IAM_CUSTOMER_EMAIL"],
                                       "password": os.environ["IAM_CUSTOMER_PASSWORD"]})
    if buyer[0] == 200:
        forbidden = call("GET", "/finance/payments", token=buyer[1]["token"])
        check("finance requires admin -> 403", forbidden[0] == 403, f"status={forbidden[0]}")
    else:
        check("finance requires admin -> 403", False, f"customer login failed {buyer[0]}")

    print()
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
