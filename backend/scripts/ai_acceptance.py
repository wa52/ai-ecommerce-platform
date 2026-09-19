"""Phase 6 验收：LLM Gateway + 商品文案 + 翻译（spec §43）。

真实模型厂商需要 API Key；本脚本启动一个本地 OpenAI 兼容的 Fake LLM 服务，
让**真实 LLMGateway / OpenAICompatibleProvider 代码**经 HTTP 调用它。

因此模型集成状态为：

    REAL_MODEL_INTEGRATION: NOT_VERIFIED

前置：ai-backend 的 LLM_BASE_URL 指向本脚本的地址（默认 http://host.docker.internal:9098/v1）。
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
PORT = int(os.environ.get("FAKE_LLM_PORT", "9098"))
EXPECTED_KEY = os.environ.get("LLM_API_KEY", "sk-sandbox-key")

failures: list[str] = []
state = {"calls": 0, "force_error": False, "force_malformed": False}

COPY_JSON = {
    "title": "Fake LLM Product Title",
    "bullets": ["卖点一", "卖点二"],
    "description": "由 Fake LLM 生成的描述",
}
TRANSLATE_JSON = {"title": "Fake English Title", "description": "English description", "bullets": ["b1"]}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        state["calls"] += 1

        if self.headers.get("Authorization") != f"Bearer {EXPECTED_KEY}":
            self._send(401, {"error": {"message": "invalid api key"}})
            return
        if state["force_error"]:
            self._send(500, {"error": {"message": "boom"}})
            return
        if state["force_malformed"]:
            self._send(200, {"unexpected": True})
            return

        stream = bool(body.get("stream"))
        user_text = json.dumps(body.get("messages", []), ensure_ascii=False)
        payload_obj = TRANSLATE_JSON if "翻译" in user_text else COPY_JSON
        content = json.dumps(payload_obj, ensure_ascii=False)

        if stream:
            chunks = [content[i : i + 8] for i in range(0, len(content), 8)]
            lines = "".join(
                f'data: {json.dumps({"choices": [{"delta": {"content": c}}]}, ensure_ascii=False)}\n\n'
                for c in chunks
            ) + "data: [DONE]\n\n"
            data = lines.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self._send(
            200,
            {
                "model": "fake-model",
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            },
        )

    def _send(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
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
        print(f"FATAL: login failed {status}")
        return 1
    token = body["token"]
    print("login: OK")

    # 1. Provider 列表与切换能力
    status, providers = call("GET", "/ai/providers", token=token)
    check("provider listed", status == 200 and providers[0]["name"] == "openai_compatible",
          f"{providers}")

    # 2. 商品文案生成
    status, copy = call("POST", "/ai/copy/product",
                        {"product_name": "陶瓷马克杯", "features": ["耐高温"], "language": "英文"}, token)
    check("product copy generated", status == 200 and copy.get("title") == COPY_JSON["title"],
          f"status={status} title={copy.get('title')}")
    check("copy returns token usage", copy.get("_meta", {}).get("usage", {}).get("total_tokens") == 33,
          f"usage={copy.get('_meta', {}).get('usage')}")

    # 3. 翻译
    status, translated = call("POST", "/ai/translate",
                              {"title": "陶瓷马克杯", "description": "描述", "bullets": ["卖点"],
                               "target_language": "英语"}, token)
    check("translation generated", status == 200 and translated.get("title") == TRANSLATE_JSON["title"],
          f"status={status} title={translated.get('title')}")

    # 4. 流式输出正常结束
    req = urllib.request.Request(
        f"{API}/ai/chat/stream",
        data=json.dumps({"prompt": "给我讲个卖点"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        streamed = resp.read().decode(errors="replace")
    check("stream terminates with done", "event: done" in streamed and "[DONE]" in streamed,
          f"len={len(streamed)}")
    check("stream delivered content", "data: " in streamed, f"chunks={streamed.count('data: ')}")

    # 5. Token Usage 记录
    status, usage = call("GET", "/ai/usage", token=token)
    check("usage recorded", status == 200 and usage["summary"]["calls"] >= 2
          and usage["summary"]["total_tokens"] >= 66,
          f"summary={usage.get('summary')}")
    check("usage attributed to caller",
          any(i["requested_by"] == EMAIL for i in usage["items"]), f"items={len(usage.get('items', []))}")

    # 6. Provider Error 处理（500 → 502，重试后仍失败）
    state["force_error"] = True
    status, err = call("POST", "/ai/copy/product", {"product_name": "x"}, token)
    check("provider error mapped (not 500 crash)", status == 502, f"status={status} detail={str(err)[:80]}")

    # 7. 模型返回异常格式不崩溃
    state["force_error"] = False
    state["force_malformed"] = True
    status, malformed = call("POST", "/ai/copy/product", {"product_name": "x"}, token)
    check("malformed model output handled", status == 502, f"status={status}")
    state["force_malformed"] = False

    # 8. 密钥不出现在错误信息/日志中
    check("secret not leaked in responses",
          EXPECTED_KEY not in json.dumps(copy) + json.dumps(err) + json.dumps(malformed),
          "no secret in payloads")

    # 9. 权限
    buyer = call("POST", "/iam/login", {"email": os.environ["IAM_CUSTOMER_EMAIL"],
                                       "password": os.environ["IAM_CUSTOMER_PASSWORD"]})
    if buyer[0] == 200:
        forbidden = call("POST", "/ai/copy/product", {"product_name": "x"}, buyer[1]["token"])
        check("ai endpoints require admin -> 403", forbidden[0] == 403, f"status={forbidden[0]}")
    else:
        check("ai endpoints require admin -> 403", False, f"customer login failed {buyer[0]}")

    server.shutdown()
    print()
    print("REAL_MODEL_INTEGRATION: NOT_VERIFIED (sandbox OpenAI-compatible server; no vendor API key)")
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
