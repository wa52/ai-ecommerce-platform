"""Agent Runtime（spec §15、§44）。

- Agent 数量与角色不写死：由 AgentRegistry 提供
- 能力通过 Tool Registry 获取
- 工具调用受与普通 API 相同的权限约束
- 工具失败必须显式处理，禁止模型编造业务数据
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.modules.ai.llm.base import LLMError, LLMMessage
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.tools.base import ToolContext, ToolPermissionError
from app.modules.ai.tools.registry import all_tools, get_tool, tool_specs

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 4

_BASE_SYSTEM = (
    "你是跨境电商运营助手。只能依据工具返回的真实业务数据回答。"
    "禁止编造销售额、订单量、利润、退款率等任何业务数字。"
    "若工具失败或没有数据，必须如实说明，不得猜测或补全数据。"
)


@dataclass
class AgentSpec:
    name: str
    description: str
    system_prompt: str = _BASE_SYSTEM
    tools: list[str] = field(default_factory=list)
    max_iterations: int = MAX_ITERATIONS


@dataclass
class ToolInvocation:
    name: str
    arguments: dict
    ok: bool
    result: Any = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {"name": self.name, "arguments": self.arguments, "ok": self.ok, "result": self.result, "error": self.error}


@dataclass
class AgentRun:
    agent: str
    answer: str
    tool_invocations: list[ToolInvocation] = field(default_factory=list)
    iterations: int = 0
    usage_total_tokens: int = 0
    duration_ms: int = 0
    stopped_reason: str = "completed"

    def as_dict(self) -> dict:
        return {
            "agent": self.agent,
            "answer": self.answer,
            "tool_invocations": [t.as_dict() for t in self.tool_invocations],
            "iterations": self.iterations,
            "usage_total_tokens": self.usage_total_tokens,
            "duration_ms": self.duration_ms,
            "stopped_reason": self.stopped_reason,
        }


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        self._agents[spec.name] = spec

    def get(self, name: str) -> AgentSpec | None:
        return self._agents.get(name)

    def list(self) -> list[dict]:
        return [
            {"name": s.name, "description": s.description, "tools": s.tools or [t.name for t in all_tools()]}
            for s in self._agents.values()
        ]


class AgentRuntime:
    def __init__(self, gateway: LLMGateway, registry: AgentRegistry):
        self._gateway = gateway
        self._registry = registry

    async def run(
        self,
        *,
        agent_name: str,
        prompt: str,
        ctx: ToolContext,
        provider: str | None = None,
        model: str | None = None,
    ) -> AgentRun:
        spec = self._registry.get(agent_name)
        if spec is None:
            raise LLMError(f"未知 Agent：{agent_name}", status_code=404)

        available = [
            t for t in all_tools() if (not spec.tools or t.name in spec.tools)
        ]
        specs = [t.spec() for t in available]

        messages = [LLMMessage("system", spec.system_prompt), LLMMessage("user", prompt)]
        run = AgentRun(agent=spec.name, answer="")
        started = time.monotonic()

        for iteration in range(1, spec.max_iterations + 1):
            run.iterations = iteration
            response = await self._gateway.complete(
                messages, provider=provider, model=model, tools=specs or None, max_tokens=800
            )
            run.usage_total_tokens += response.usage.total_tokens

            if not response.tool_calls:
                run.answer = response.content
                break

            messages.append(
                LLMMessage(role="assistant", content=response.content, tool_calls=response.tool_calls)
            )

            for call in response.tool_calls:
                invocation = await self._invoke(call.name, call.arguments, ctx)
                run.tool_invocations.append(invocation)
                messages.append(
                    LLMMessage(
                        role="tool",
                        tool_call_id=call.id,
                        name=call.name,
                        content=json.dumps(
                            {
                                "ok": invocation.ok,
                                "data": invocation.result,
                                "error": invocation.error,
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
        else:
            run.stopped_reason = "max_iterations"
            run.answer = "已达到最大工具调用轮次，未能给出最终结论。"

        run.duration_ms = int((time.monotonic() - started) * 1000)
        return run

    async def _invoke(self, name: str, raw_arguments: str, ctx: ToolContext) -> ToolInvocation:
        tool = get_tool(name)
        if tool is None:
            return ToolInvocation(name=name, arguments={}, ok=False, error=f"未知工具：{name}")

        try:
            arguments = json.loads(raw_arguments or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("参数必须是 JSON 对象")
        except (json.JSONDecodeError, ValueError) as exc:
            return ToolInvocation(name=name, arguments={}, ok=False, error=f"工具参数解析失败：{exc}")

        try:
            tool.check_permission(ctx)
        except ToolPermissionError as exc:
            return ToolInvocation(name=name, arguments=arguments, ok=False, error=str(exc))

        try:
            result = await tool.run(ctx, arguments)
        except Exception as exc:  # noqa: BLE001 - 工具异常必须显式返回，不得静默
            logger.warning("tool %s raised: %s", name, type(exc).__name__)
            return ToolInvocation(name=name, arguments=arguments, ok=False, error=f"工具执行异常：{type(exc).__name__}")

        return ToolInvocation(
            name=name, arguments=arguments, ok=result.ok, result=result.data, error=result.error
        )


def build_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(
        AgentSpec(
            name="operations",
            description="运营助手：商品/订单/销售/财务数据分析",
            tools=[
                "commerce.search_products",
                "commerce.recent_orders",
                "finance.summary",
                "analytics.sales_summary",
            ],
        )
    )
    registry.register(
        AgentSpec(
            name="probe",
            description="验收探针：工具失败与权限约束验证",
            tools=["debug.always_fails", "debug.admin_only"],
        )
    )
    return registry
