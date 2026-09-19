import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.ai.agent.api import get_llm_gateway
from app.modules.ai.agent.runtime import AgentRegistry, AgentRuntime, AgentSpec, build_registry
from app.modules.ai.llm.base import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMUsage, ToolCall
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.tools.base import Tool, ToolContext, ToolResult
from app.modules.ai.tools.registry import all_tools, get_tool, tool_specs
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)
CUSTOMER = CurrentUser(id="U2", email="buyer@example.com", is_staff=False)


class _NoopProvider(LLMProvider):
    name = "stub"

    async def complete(self, messages, *, model, temperature=0.7, max_tokens=1024, tools=None):
        return LLMResponse(content="", model=model, provider=self.name)

    async def stream(self, messages, *, model, temperature=0.7, max_tokens=1024):
        if False:  # pragma: no cover
            yield ""


class ScriptedGateway(LLMGateway):
    """按脚本依次返回响应，用于验证工具选择与最终回答。"""

    def __init__(self, scripted: list[LLMResponse]):
        super().__init__({"stub": _NoopProvider()}, default_provider="stub", model="stub-model")
        self._scripted = list(scripted)
        self.seen_messages: list[list[LLMMessage]] = []
        self.seen_tools: list[list[dict] | None] = []

    async def complete(self, messages, *, provider=None, model=None, temperature=0.7, max_tokens=1024, tools=None):
        self.seen_messages.append(list(messages))
        self.seen_tools.append(tools)
        if not self._scripted:
            return LLMResponse(content="(no more scripted responses)", model="stub", provider="stub")
        return self._scripted.pop(0)


def _tool_call(name: str, arguments: dict, call_id: str = "call_1") -> LLMResponse:
    return LLMResponse(
        content="",
        model="stub",
        provider="stub",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=json.dumps(arguments))],
        usage=LLMUsage(5, 5, 10),
    )


def _final(text: str) -> LLMResponse:
    return LLMResponse(content=text, model="stub", provider="stub", usage=LLMUsage(3, 4, 7))


class RecordingTool(Tool):
    name = "test.record"
    description = "记录调用参数"
    parameters = {"type": "object", "properties": {"q": {"type": "string"}}}
    requires_admin = True

    def __init__(self):
        self.calls: list[dict] = []

    async def run(self, ctx: ToolContext, arguments: dict) -> ToolResult:
        self.calls.append(arguments)
        return ToolResult(ok=True, data={"echo": arguments})


def _registry_with(*tools: Tool) -> AgentRegistry:
    from app.modules.ai.tools import registry as tool_registry

    for t in tools:
        tool_registry._TOOLS[t.name] = t
    registry = AgentRegistry()
    registry.register(AgentSpec(name="test-agent", description="t", tools=[t.name for t in tools]))
    return registry


# ---------- registry ----------


def test_builtin_tools_registered_and_specs_valid():
    names = {t.name for t in all_tools()}
    assert {"commerce.search_products", "commerce.recent_orders", "finance.summary", "analytics.sales_summary"} <= names
    for spec in tool_specs():
        assert spec["type"] == "function"
        assert spec["function"]["name"]
        assert "parameters" in spec["function"]


def test_agent_registry_lists_agents():
    agents = build_registry().list()
    assert {a["name"] for a in agents} == {"operations", "probe"}
    assert "analytics.sales_summary" in agents[0]["tools"]


# ---------- runtime ----------


@pytest.mark.asyncio
async def test_tool_selection_arguments_result_and_final_answer():
    tool = RecordingTool()
    gateway = ScriptedGateway([_tool_call("test.record", {"q": "杯子"}), _final("查到 1 个结果")])
    runtime = AgentRuntime(gateway, _registry_with(tool))

    run = await runtime.run(agent_name="test-agent", prompt="查杯子", ctx=ToolContext(user=ADMIN))

    assert [t.name for t in run.tool_invocations] == ["test.record"]
    assert run.tool_invocations[0].arguments == {"q": "杯子"}  # Tool Arguments
    assert run.tool_invocations[0].ok is True  # Tool Result
    assert run.tool_invocations[0].result == {"echo": {"q": "杯子"}}
    assert tool.calls == [{"q": "杯子"}]
    assert run.answer == "查到 1 个结果"  # Agent Final Answer
    assert run.iterations == 2
    assert run.usage_total_tokens == 17


@pytest.mark.asyncio
async def test_tool_failure_is_surfaced_not_fabricated():
    from app.modules.ai.tools.builtin import ToolFailureProbeTool

    failing = ToolFailureProbeTool()
    gateway = ScriptedGateway([_tool_call("debug.always_fails", {}), _final("工具失败，无法给出数据")])
    runtime = AgentRuntime(gateway, _registry_with(failing))

    run = await runtime.run(agent_name="test-agent", prompt="触发失败", ctx=ToolContext(user=ADMIN))
    assert run.tool_invocations[0].ok is False
    assert "失败" in (run.tool_invocations[0].error or "")
    # 失败信息被回传给模型（role=tool），而非静默忽略
    tool_messages = [m for m in gateway.seen_messages[1] if m.role == "tool"]
    assert tool_messages and json.loads(tool_messages[0].content)["ok"] is False
    assert run.answer == "工具失败，无法给出数据"


@pytest.mark.asyncio
async def test_permission_enforced_for_tools():
    tool = RecordingTool()  # requires_admin = True
    gateway = ScriptedGateway([_tool_call("test.record", {"q": "x"}), _final("done")])
    runtime = AgentRuntime(gateway, _registry_with(tool))

    run = await runtime.run(agent_name="test-agent", prompt="查", ctx=ToolContext(user=CUSTOMER))
    assert run.tool_invocations[0].ok is False
    assert "管理员权限" in (run.tool_invocations[0].error or "")
    assert tool.calls == []  # 工具未被实际执行


@pytest.mark.asyncio
async def test_invalid_tool_arguments_are_rejected():
    gateway = ScriptedGateway(
        [LLMResponse(content="", model="s", provider="s",
                     tool_calls=[ToolCall(id="c1", name="test.record", arguments="{not-json")]), _final("ok")]
    )
    runtime = AgentRuntime(gateway, _registry_with(RecordingTool()))
    run = await runtime.run(agent_name="test-agent", prompt="x", ctx=ToolContext(user=ADMIN))
    assert run.tool_invocations[0].ok is False
    assert "参数解析失败" in (run.tool_invocations[0].error or "")


@pytest.mark.asyncio
async def test_unknown_tool_is_reported():
    gateway = ScriptedGateway([_tool_call("nope.tool", {}), _final("ok")])
    runtime = AgentRuntime(gateway, _registry_with(RecordingTool()))
    run = await runtime.run(agent_name="test-agent", prompt="x", ctx=ToolContext(user=ADMIN))
    assert run.tool_invocations[0].ok is False
    assert "未知工具" in (run.tool_invocations[0].error or "")


@pytest.mark.asyncio
async def test_max_iterations_stops_run():
    tool = RecordingTool()
    gateway = ScriptedGateway([_tool_call("test.record", {"q": str(i)}) for i in range(10)])
    registry = _registry_with(tool)
    registry.get("test-agent").max_iterations = 2  # type: ignore[union-attr]
    runtime = AgentRuntime(gateway, registry)

    run = await runtime.run(agent_name="test-agent", prompt="loop", ctx=ToolContext(user=ADMIN))
    assert run.stopped_reason == "max_iterations"
    assert run.iterations == 2
    assert "最大工具调用轮次" in run.answer


@pytest.mark.asyncio
async def test_unknown_agent_raises():
    runtime = AgentRuntime(ScriptedGateway([]), build_registry())
    with pytest.raises(LLMError):
        await runtime.run(agent_name="ghost", prompt="x", ctx=ToolContext(user=ADMIN))


@pytest.mark.asyncio
async def test_tools_are_passed_to_model():
    gateway = ScriptedGateway([_final("直接回答")])
    runtime = AgentRuntime(gateway, _registry_with(RecordingTool()))
    await runtime.run(agent_name="test-agent", prompt="x", ctx=ToolContext(user=ADMIN))
    assert gateway.seen_tools[0] and gateway.seen_tools[0][0]["function"]["name"] == "test.record"


# ---------- real tools against real (Saleor) data ----------


@pytest.mark.asyncio
async def test_sales_summary_handles_no_data_without_fabrication(monkeypatch):
    from app.modules.ai.tools import builtin

    class _EmptyCommerce:
        async def list_orders(self, **kwargs):
            from app.modules.commerce.domain.models import Page

            return [], Page(total_count=0, has_next_page=False, end_cursor=None)

    monkeypatch.setattr(builtin, "CommerceService", lambda *a, **k: _EmptyCommerce())
    result = await builtin.SalesSummaryTool().run(ToolContext(user=ADMIN, token="t"), {"limit": 5})
    assert result.ok is True
    assert result.data["order_count"] == 0
    assert "暂无订单数据" in result.data["note"]


@pytest.mark.asyncio
async def test_tool_reports_commerce_error_as_failure(monkeypatch):
    from app.modules.ai.tools import builtin
    from app.modules.commerce.application.service import CommerceError

    class _FailingCommerce:
        async def list_orders(self, **kwargs):
            raise CommerceError("上游不可用", status_code=502)

    monkeypatch.setattr(builtin, "CommerceService", lambda *a, **k: _FailingCommerce())
    result = await builtin.RecentOrdersTool().run(ToolContext(user=ADMIN, token="t"), {"limit": 5})
    assert result.ok is False
    assert "上游不可用" in (result.error or "")


# ---------- API ----------


def _client(gateway: LLMGateway, user: CurrentUser) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_llm_gateway] = lambda: gateway
    return TestClient(app)


def test_agent_endpoints_list_agents_and_tools():
    client = _client(ScriptedGateway([]), ADMIN)
    assert client.get("/api/v1/agent/agents").status_code == 200
    tools = client.get("/api/v1/agent/tools").json()
    assert any(t["name"] == "analytics.sales_summary" for t in tools)


def test_agent_run_returns_trace():
    tool = RecordingTool()
    gateway = ScriptedGateway([_tool_call("test.record", {"q": "a"}), _final("最终回答")])
    from app.modules.ai.agent import api as agent_api

    client = _client(gateway, ADMIN)
    # 用测试 Agent 覆盖默认注册表
    original = agent_api.build_registry
    agent_api.build_registry = lambda: _registry_with(tool)
    try:
        resp = client.post("/api/v1/agent/run", json={"agent": "test-agent", "prompt": "查 a"})
    finally:
        agent_api.build_registry = original

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "最终回答"
    assert body["tool_invocations"][0]["name"] == "test.record"
    assert body["tool_invocations"][0]["ok"] is True


def test_agent_run_admin_endpoint_forbids_customer():
    client = _client(ScriptedGateway([]), CUSTOMER)
    resp = client.post("/api/v1/agent/run/admin", json={"agent": "operations", "prompt": "x"})
    assert resp.status_code == 403
