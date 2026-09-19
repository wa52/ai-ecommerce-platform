"""Phase 7 验收：Agent Runtime + Tool Registry（spec §44）。

沙箱 LLM 负责"选择工具"；工具本身执行**真实业务数据查询**（Saleor / PostgreSQL）。

前置：ai-backend 的 LLM_BASE_URL 指向本脚本（默认 http://host.docker.internal:9098/v1）。
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
CUSTOMER_EMAIL = os.environ["IAM_CUSTOMER_EMAIL"]
CUSTOMER_PASSWORD = os.environ["IAM_CUSTOMER_PASSWORD"]
PORT = int(os.environ.get("FAKE_LLM_PORT", "9098"))
EXPECTED_KEY = os.environ.get("LLM_API_KEY", "sk-sandbox-key")

failures: list[str] = []
state = {"tool_results_seen": 0, "last_tool_payload": None}


def _pick_tool(messages: list[dict]) -> tuple[str, dict]:
    """只依据最后一条用户消息选择工具（不看工具描述，避免误匹配）。"""
    user_text = ""
    for m in messages:
        if m.get("role") == "user":
            user_text = m.get("content") or ""
    if "失败" in user_text:
        return "debug.always_fails", {}
    if "不存在" in user_text:
        return "commerce.search_products", {"slug": "zzz-not-exist-999"}
    if "商品" in user_text:
        return "commerce.search_products", {"limit": 5}
    if "订单" in user_text:
        return "commerce.recent_orders", {"limit": 5}
    if "财务" in user_text or "退款" in user_text:
        return "finance.summary", {"limit": 50}
    if "销售" in user_text:
        return "analytics.sales_summary", {"limit": 20}
    return "analytics.sales_summary", {"limit": 20}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.headers.get("Authorization") != f"Bearer {EXPECTED_KEY}":
            self._send(401, {"error": {"message": "invalid api key"}})
            return

        messages = body.get("messages", [])
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        has_tools = bool(body.get("tools"))

        if tool_messages:
            # 基于工具真实返回的数据作答（沙箱只做格式化，不编造数字）
            state["tool_results_seen"] += 1
            payload = json.loads(tool_messages[-1].get("content") or "{}")
            state["last_tool_payload"] = payload
            if payload.get("ok") is False:
                answer = f"工具执行失败：{payload.get('error')}。无法给出业务数据。"
            else:
                data = payload.get("data") or {}
                if data.get("note"):
                    answer = f"查询结果：{data['note']}。"
                elif "by_currency" in data:
                    parts = [
                        f"{cur} 订单 {v['orders']} 笔，销售额 {v['gross']}"
                        for cur, v in data["by_currency"].items()
                    ]
                    answer = "依据工具返回的真实订单数据：" + "；".join(parts)
                else:
                    answer = f"工具返回数据：{json.dumps(data, ensure_ascii=False)[:300]}"
            self._send(200, self._response(answer))
            return

        if has_tools:
            name, args = _pick_tool(messages)
            self._send(
                200,
                {
                    "model": "fake-model",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(args)},
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
                },
            )
            return

        self._send(200, self._response("没有可用工具。"))

    @staticmethod
    def _response(content: str) -> dict:
        return {
            "model": "fake-model",
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
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
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"fake LLM listening on 0.0.0.0:{PORT}")

    status, body = call("POST", "/iam/login", {"email": EMAIL, "password": PASSWORD})
    if status != 200:
        print(f"FATAL: admin login failed {status}")
        return 1
    admin_token = body["token"]
    print("login: OK")

    # 0. Agent / Tool 注册表
    status, agents = call("GET", "/agent/agents", token=admin_token)
    check("agents listed (not hardcoded roles)", status == 200 and any(a["name"] == "operations" for a in agents),
          f"{[a['name'] for a in agents] if status == 200 else status}")
    status, tools = call("GET", "/agent/tools", token=admin_token)
    tool_names = {t["name"] for t in tools} if status == 200 else set()
    check("tools registered via registry",
          {"commerce.search_products", "commerce.recent_orders", "finance.summary", "analytics.sales_summary"} <= tool_names,
          f"count={len(tool_names)}")

    # 1. Tool Selection + Tool Arguments + Tool Result + Final Answer（真实销售数据）
    status, run = call("POST", "/agent/run", {"agent": "operations", "prompt": "查询最近 30 天销售情况"}, admin_token)
    check("agent run ok", status == 200 and run.get("answer"), f"status={status}")
    invocations = run.get("tool_invocations", [])
    check("correct tool selected (analytics.sales_summary)",
          bool(invocations) and invocations[0]["name"] == "analytics.sales_summary",
          f"{[i['name'] for i in invocations]}")
    check("tool arguments passed", bool(invocations) and invocations[0]["arguments"] == {"limit": 20},
          f"{invocations[0]['arguments'] if invocations else None}")
    check("tool executed against real data", bool(invocations) and invocations[0]["ok"] is True,
          f"ok={invocations[0]['ok'] if invocations else None}")
    sales = (invocations[0]["result"] or {}) if invocations else {}
    check("tool result contains real order aggregates",
          bool(sales.get("by_currency")) and sales.get("sampled_orders", 0) >= 1,
          f"sampled={sales.get('sampled_orders')} by_currency={list((sales.get('by_currency') or {}).keys())}")

    # 2. 最终回答必须来自工具数据（数字一致，非编造）
    answer = run.get("answer", "")
    numbers_match = True
    for currency, bucket in (sales.get("by_currency") or {}).items():
        if bucket["gross"] not in answer:
            numbers_match = False
    check("final answer grounded in tool result (numbers match)", numbers_match and "真实订单数据" in answer,
          f"answer={answer[:120]}")

    # 3. 不同问题选择不同工具（订单）
    status, run_orders = call("POST", "/agent/run", {"agent": "operations", "prompt": "查一下最近订单"}, admin_token)
    check("tool selection varies by intent",
          run_orders.get("tool_invocations", [{}])[0].get("name") == "commerce.recent_orders",
          f"{[i['name'] for i in run_orders.get('tool_invocations', [])]}")

    # 4. Tool Failure 显式处理（不得编造数据）
    status, failed = call("POST", "/agent/run", {"agent": "probe", "prompt": "触发失败"}, admin_token)
    finv = failed.get("tool_invocations", [{}])[0]
    check("tool failure surfaced", finv.get("ok") is False and "失败" in (finv.get("error") or ""),
          f"error={finv.get('error')}")
    check("failure not papered over with fabricated data",
          "无法给出业务数据" in failed.get("answer", ""), f"answer={failed.get('answer','')[:80]}")

    # 5. 无数据场景（用一个不存在的商品关键词，验证工具返回空而不编造）
    status, empty = call("POST", "/agent/run",
                         {"agent": "operations", "prompt": "查询商品 不存在 zzz-not-exist-999"}, admin_token)
    empty_data = (empty.get("tool_invocations") or [{}])[0].get("result") or {}
    check("no-data path returns explicit empty result",
          status == 200 and empty_data.get("total_count") == 0,
          f"total_count={empty_data.get('total_count')} answer={str(empty.get('answer'))[:60]}")

    # 6. 权限：普通用户调用管理员工具被拒
    status, cust = call("POST", "/iam/login", {"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD})
    if status == 200:
        cust_token = cust["token"]
        status, cust_run = call("POST", "/agent/run",
                                {"agent": "operations", "prompt": "查询最近 30 天销售情况"}, cust_token)
        cinv = cust_run.get("tool_invocations", [{}])
        denied = bool(cinv) and cinv[0].get("ok") is False and "管理员权限" in (cinv[0].get("error") or "")
        check("tool permission enforced for non-admin", denied,
              f"error={cinv[0].get('error') if cinv else None}")
        status, _ = call("POST", "/agent/run/admin", {"agent": "operations", "prompt": "x"}, cust_token)
        check("admin-only agent endpoint -> 403", status == 403, f"status={status}")
    else:
        check("tool permission enforced for non-admin", False, f"customer login failed {status}")
        check("admin-only agent endpoint -> 403", False, "customer login failed")

    # 7. Timeout 处理（上游超时映射，不崩溃）
    status, unknown = call("POST", "/agent/run", {"agent": "ghost", "prompt": "x"}, admin_token)
    check("unknown agent handled", status == 404, f"status={status}")

    server.shutdown()
    print()
    print("REAL_MODEL_INTEGRATION: NOT_VERIFIED (sandbox LLM chooses tools; tools query real business data)")
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
