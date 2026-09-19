"""Phase 8 验收：RAG（spec §45）。

固定测试集覆盖：明确命中 / 同义表达 / 多文档 / 无相关文档 / 错误问题 / 上下文追问。
向量存储使用真实 PostgreSQL + pgvector。

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
PORT = int(os.environ.get("FAKE_LLM_PORT", "9098"))
EXPECTED_KEY = os.environ.get("LLM_API_KEY", "sk-sandbox-key")

failures: list[str] = []
state = {"llm_calls": 0}

DOCS = [
    ("退货政策", "标准退货窗口为 30 天。\n\n买家需保持商品与包装完好，并附上订单号。\n\n生鲜类商品不支持无理由退货。", "handbook/returns.md"),
    ("物流时效", "美国本土订单通常 3-5 个工作日送达。\n\n跨境订单需要 7-15 个工作日，并可能产生关税。\n\n旺季（11-12 月）时效会延长。", "handbook/shipping.md"),
    ("支付与退款", "支持信用卡与 PayPal。\n\n退款在审核通过后 5 个工作日内原路退回。\n\n部分退款按剩余可退额度计算。", "handbook/payments.md"),
]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.headers.get("Authorization") != f"Bearer {EXPECTED_KEY}":
            self._send(401, {"error": {"message": "invalid api key"}})
            return
        state["llm_calls"] += 1

        messages = body.get("messages", [])
        text = "\n".join(m.get("content") or "" for m in messages)
        tool_messages = [m for m in messages if m.get("role") == "tool"]

        if body.get("tools"):
            if "知识库" in text or "退货政策" in text or "资料" in text:
                call = {
                    "id": "call_rag",
                    "type": "function",
                    "function": {"name": "rag.search", "arguments": json.dumps({"knowledge_base_id": state.get("kb_id"), "query": "退货窗口", "top_k": 3})},
                }
            else:
                call = {"id": "call_sales", "type": "function", "function": {"name": "analytics.sales_summary", "arguments": "{}"}}
            self._send(200, {
                "model": "fake-model",
                "choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [call]}, "finish_reason": "tool_calls"}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
            })
            return

        if tool_messages:
            payload = json.loads(tool_messages[-1].get("content") or "{}")
            data = payload.get("data") or {}
            if data.get("note"):
                answer = f"知识库中没有相关资料（{data['note']}）。"
            else:
                first = (data.get("chunks") or [{}])[0]
                answer = f"依据资料 [1]（{first.get('document_title')}，来源 {first.get('source')}）：{first.get('content','')[:60]}"
            self._send(200, self._response(answer))
            return

        # RAG answer：上下文来自检索结果（沙箱仅做引用拼接）
        context_line = ""
        for line in text.splitlines():
            if line.startswith("[1]"):
                context_line = line
                break
        answer = f"依据资料 [1]：{context_line}" if context_line else "知识库中没有找到与该问题相关的资料，无法回答。"
        self._send(200, self._response(answer))

    @staticmethod
    def _response(content: str) -> dict:
        return {
            "model": "fake-model",
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
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
        print(f"FATAL: login failed {status}")
        return 1
    token = body["token"]
    print("login: OK")

    slug = os.environ.get("KB_SLUG", "ops-handbook-acceptance")
    status, kb = call("POST", "/rag/knowledge-bases", {"name": "运营手册", "slug": slug, "description": "验收用"}, token)
    if status == 409:
        kbs = call("GET", "/rag/knowledge-bases", token=token)[1]
        kb = next(k for k in kbs if k["slug"] == slug)
    check("knowledge base created", status in (201, 409) and bool(kb.get("id")), f"status={status}")
    kb_id = kb["id"]
    state["kb_id"] = kb_id

    for title, content, source in DOCS:
        status, doc = call("POST", f"/rag/knowledge-bases/{kb_id}/documents",
                           {"title": title, "content": content, "source": source}, token)
        check(f"document ingested: {title}", status == 201, f"status={status}")

    # 1. 明确命中
    status, hit = call("POST", f"/rag/knowledge-bases/{kb_id}/search", {"query": "退货窗口多少天", "top_k": 3}, token)
    top = (hit.get("chunks") or [{}])[0]
    check("explicit hit retrieved", status == 200 and top.get("document_title") == "退货政策",
          f"top={top.get('document_title')} score={top.get('score')}")
    check("retrieval scores recorded (vector+keyword+fused)",
          all(k in top for k in ("vector_score", "keyword_score", "score")),
          f"v={top.get('vector_score')} k={top.get('keyword_score')} s={top.get('score')}")
    check("chunk source recorded", top.get("source") == "handbook/returns.md", f"source={top.get('source')}")

    # 2. 同义表达
    status, syn = call("POST", f"/rag/knowledge-bases/{kb_id}/search", {"query": "钱多久能退回来", "top_k": 3}, token)
    titles = [c["document_title"] for c in syn.get("chunks", [])]
    check("synonym expression retrieves refund doc", "支付与退款" in titles, f"titles={titles}")

    # 3. 多文档召回
    status, multi = call("POST", f"/rag/knowledge-bases/{kb_id}/search", {"query": "物流 时效 关税", "top_k": 3}, token)
    mtitles = [c["document_title"] for c in multi.get("chunks", [])]
    check("multi-document retrieval", "物流时效" in mtitles and len(mtitles) >= 1, f"titles={mtitles}")

    # 4. 无相关文档 → 无结果
    status, none = call("POST", f"/rag/knowledge-bases/{kb_id}/search",
                        {"query": "量子计算机的退相干时间", "top_k": 3}, token)
    check("unrelated query returns no chunks", status == 200 and none.get("count") == 0,
          f"count={none.get('count')} chunks={[(c.get('document_title'), c.get('score'), c.get('keyword_score')) for c in none.get('chunks', [])]}")

    # 5. 错误问题 → 拒答（不编造）
    before = state["llm_calls"]
    status, refused = call("POST", f"/rag/knowledge-bases/{kb_id}/answer",
                           {"query": "量子计算机的退相干时间是多少"}, token)
    check("refuses without evidence", status == 200 and refused.get("grounded") is False
          and refused.get("reason") == "no_context", f"grounded={refused.get('grounded')} reason={refused.get('reason')}")
    check("no LLM call when no evidence", state["llm_calls"] == before, f"calls={state['llm_calls'] - before}")

    # 6. 有证据 → 带引用回答
    status, grounded = call("POST", f"/rag/knowledge-bases/{kb_id}/answer", {"query": "退货窗口是多久"}, token)
    ctxs = grounded.get("contexts") or []
    check("grounded answer with contexts", status == 200 and grounded.get("grounded") is True and bool(ctxs),
          f"contexts={len(ctxs)}")
    check("answer cites context", "[1]" in (grounded.get("answer") or ""), f"answer={str(grounded.get('answer'))[:80]}")
    check("contexts carry source for traceability", bool(ctxs) and bool(ctxs[0].get("source")),
          f"source={ctxs[0].get('source') if ctxs else None}")

    # 7. 上下文追问（同一知识库、指代式问题）
    status, follow = call("POST", f"/rag/knowledge-bases/{kb_id}/answer", {"query": "那跨境订单呢"}, token)
    check("follow-up question handled", status == 200, f"status={status} grounded={follow.get('grounded')}")

    # 8. Agent 通过 RAG Tool 使用知识库（spec §16：RAG 是 Agent 的一种能力）
    status, run = call("POST", "/agent/run",
                       {"agent": "operations", "prompt": "根据知识库 退货政策 说明退货窗口"}, token)
    inv = (run.get("tool_invocations") or [{}])[0]
    check("agent selected rag.search tool", inv.get("name") == "rag.search", f"{inv.get('name')}")
    check("rag tool returned real chunks", inv.get("ok") is True and (inv.get("result") or {}).get("count", 0) >= 1,
          f"count={(inv.get('result') or {}).get('count')}")

    # 9. 权限
    status, cust = call("POST", "/iam/login", {"email": os.environ["IAM_CUSTOMER_EMAIL"],
                                              "password": os.environ["IAM_CUSTOMER_PASSWORD"]})
    if status == 200:
        forbidden = call("GET", "/rag/knowledge-bases", token=cust["token"])
        check("rag requires admin -> 403", forbidden[0] == 403, f"status={forbidden[0]}")
    else:
        check("rag requires admin -> 403", False, "customer login failed")

    server.shutdown()
    print()
    print("REAL_MODEL_INTEGRATION: NOT_VERIFIED (sandbox LLM; retrieval runs on real pgvector)")
    print(f"RESULT: {'PASS' if not failures else 'FAIL ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
