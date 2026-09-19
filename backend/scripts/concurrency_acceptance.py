"""并发验收（spec §38.3 并发更新 / §41 重复请求）。

1) 并发库存更新：同一 SKU 并发写入 N 次，验证最终库存为其中一次写入值，
   且不会出现负数或重复库存行。
2) 并发重复支付：同一 idempotency_key 并发请求，验证只产生一笔有效交易。
"""

import concurrent.futures as futures
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("AI_API_URL", "http://localhost:8001/api/v1")
EMAIL = os.environ["IAM_ADMIN_EMAIL"]
PASSWORD = os.environ["IAM_ADMIN_PASSWORD"]
RUN = os.environ.get("RUN_ID", "conc")

failures: list[str] = []


def call(method: str, path: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 204:
                return 204, {}
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

    # ---------- 1. 并发库存更新 ----------
    status, inv = call("GET", "/commerce/inventory?first=100", token=token)
    rows = inv.get("items", []) if status == 200 else []
    if not rows:
        check("concurrent inventory update", False, "没有可用 SKU")
    else:
        variant_id = rows[0]["variant_id"]
        warehouses = call("GET", "/commerce/warehouses", token=token)[1]
        warehouse_id = warehouses[0]["id"]

        quantities = list(range(11, 21))  # 10 个并发写入
        with futures.ThreadPoolExecutor(max_workers=10) as pool:
            results = list(
                pool.map(
                    lambda q: call(
                        "POST",
                        "/commerce/inventory",
                        {"variant_id": variant_id, "warehouse_id": warehouse_id, "quantity": q},
                        token,
                    ),
                    quantities,
                )
            )
        ok = [r for r in results if r[0] == 200]
        check("concurrent writes accepted (no 5xx)",
              len(ok) == len(quantities) and all(r[0] < 500 for r in results),
              f"accepted={len(ok)}/{len(quantities)} statuses={sorted({r[0] for r in results})}")

        status, after = call("GET", "/commerce/inventory?first=100", token=token)
        final_rows = [r for r in after.get("items", []) if r["variant_id"] == variant_id]
        final_qty = final_rows[0]["quantity"] if final_rows else None
        check("final quantity is one of the written values (no lost/duplicated writes)",
              final_qty in quantities, f"final={final_qty} written={quantities}")
        check("no duplicate stock rows for same variant/warehouse",
              len({(r["variant_id"], r["warehouse"]) for r in final_rows}) == len(final_rows),
              f"rows={len(final_rows)}")
        check("stock never negative", all(r["quantity"] >= 0 for r in after.get("items", [])),
              f"min={min((r['quantity'] for r in after.get('items', [])), default=0)}")

    # ---------- 2. 并发重复支付（幂等） ----------
    key = f"{RUN}-conc-pay"
    payload = {"order_ref": f"{RUN}-order", "provider": "stripe", "amount": "50.00",
               "currency": "USD", "idempotency_key": key}
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        payments = list(pool.map(lambda _: call("POST", "/finance/payments", payload, token), range(8)))

    ids = {p[1]["id"] for p in payments if p[0] == 201}
    created_flags = [p[1].get("created") for p in payments if p[0] == 201]
    check("concurrent duplicate payment -> single transaction",
          len(ids) == 1 and created_flags.count(True) == 1,
          f"ids={len(ids)} created_true={created_flags.count(True)} statuses={sorted({p[0] for p in payments})}")

    status, listed = call("GET", "/finance/payments?limit=200", token=token)
    same_key = [p for p in listed if p["idempotency_key"] == key] if status == 200 else []
    check("only one payment row for the idempotency key", len(same_key) == 1, f"rows={len(same_key)}")

    print()
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
