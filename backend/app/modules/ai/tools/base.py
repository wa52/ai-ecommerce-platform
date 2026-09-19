"""Agent 能力（Tool / Capability）抽象（spec §15）。

新增 AI 能力时优先新增 Tool，而不是修改 Agent Runtime 核心。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.modules.iam.domain.models import CurrentUser


@dataclass
class ToolContext:
    """工具执行上下文：权限与调用者令牌（与普通 API 同等约束，spec §44）。"""

    user: CurrentUser
    token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return self.user.is_admin


@dataclass
class ToolResult:
    ok: bool
    data: Any = None
    error: str | None = None

    def as_dict(self) -> dict:
        return {"ok": self.ok, "data": self.data, "error": self.error}


class ToolPermissionError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    requires_admin: bool = True

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def check_permission(self, ctx: ToolContext) -> None:
        if self.requires_admin and not ctx.is_admin:
            raise ToolPermissionError(f"工具 {self.name} 需要管理员权限")

    @abstractmethod
    async def run(self, ctx: ToolContext, arguments: dict[str, Any]) -> ToolResult: ...
