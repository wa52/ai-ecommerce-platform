"""Tool / Capability 注册表（spec §15）。

新增能力只注册 Tool，不改 Agent Runtime。
"""

from app.modules.ai.tools.base import Tool

_TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    if tool.name in _TOOLS:
        raise ValueError(f"工具名重复：{tool.name}")
    _TOOLS[tool.name] = tool
    return tool


def get_tool(name: str) -> Tool | None:
    return _TOOLS.get(name)


def all_tools() -> list[Tool]:
    return list(_TOOLS.values())


def tool_specs() -> list[dict]:
    return [t.spec() for t in _TOOLS.values()]


def _load_builtin() -> None:
    from app.modules.ai.tools import builtin

    for name in (
        "SearchProductsTool",
        "RecentOrdersTool",
        "FinanceSummaryTool",
        "SalesSummaryTool",
        "ToolFailureProbeTool",
        "AdminOnlyProbeTool",
    ):
        register(getattr(builtin, name)())


_load_builtin()
