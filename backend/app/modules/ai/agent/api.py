from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.modules.ai.agent.runtime import AgentRuntime, build_registry
from app.modules.ai.api.routes import get_llm_gateway
from app.modules.ai.llm.base import LLMError
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.tools.base import ToolContext
from app.modules.ai.tools.registry import all_tools
from app.modules.iam.api.deps import AdminUserDep, BearerTokenDep, CurrentUserDep

router = APIRouter(prefix="/agent", tags=["agent"])

GatewayDep = Annotated[LLMGateway, Depends(get_llm_gateway)]


class AgentRunRequest(BaseModel):
    agent: str = Field(default="operations", max_length=50)
    prompt: str = Field(min_length=1, max_length=4000)
    provider: str | None = None
    model: str | None = None


@router.get("/agents")
async def list_agents(_: CurrentUserDep) -> list[dict]:
    return build_registry().list()


@router.get("/tools")
async def list_tools(_: CurrentUserDep) -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "requires_admin": t.requires_admin}
        for t in all_tools()
    ]


@router.post("/run")
async def run_agent(
    req: AgentRunRequest,
    user: CurrentUserDep,
    token: BearerTokenDep,
    gateway: GatewayDep,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """运行 Agent。工具调用与普通 API 受同等权限约束（spec §44）。"""
    runtime = AgentRuntime(gateway, build_registry())
    ctx = ToolContext(user=user, token=token, extra={"session_factory": None, "db": db})
    try:
        run = await runtime.run(
            agent_name=req.agent, prompt=req.prompt, ctx=ctx, provider=req.provider, model=req.model
        )
    except LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return run.as_dict()


@router.post("/run/admin")
async def run_agent_admin(
    req: AgentRunRequest,
    user: AdminUserDep,
    token: BearerTokenDep,
    gateway: GatewayDep,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """管理员专用入口（用于对比权限约束）。"""
    return await run_agent(req, user, token, gateway, db)
