from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.modules.ai.application.content import AiContentError, AiContentService
from app.modules.ai.llm.base import LLMError, LLMMessage
from app.modules.ai.llm.gateway import LLMGateway, build_gateway
from app.modules.ai.llm.usage import UsageRepository
from app.modules.iam.api.deps import AdminUserDep
from app.infrastructure.config.settings import get_settings

router = APIRouter(prefix="/ai", tags=["ai"])


def get_llm_gateway() -> LLMGateway:
    return build_gateway(get_settings())


GatewayDep = Annotated[LLMGateway, Depends(get_llm_gateway)]


class CopyRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=250)
    features: list[str] = Field(default_factory=list)
    language: str = Field(default="中文", max_length=40)
    provider: str | None = None
    model: str | None = None


class TranslateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: str | None = None
    bullets: list[str] = Field(default_factory=list)
    target_language: str = Field(min_length=1, max_length=40)
    provider: str | None = None
    model: str | None = None


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    system: str | None = Field(default=None, max_length=2000)
    provider: str | None = None
    model: str | None = None


@router.get("/providers")
async def list_providers(_: AdminUserDep, gateway: GatewayDep) -> list[dict]:
    return gateway.list_providers()


@router.post("/copy/product")
async def generate_product_copy(
    req: CopyRequest,
    user: AdminUserDep,
    gateway: GatewayDep,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AiContentService(gateway, db)
    try:
        return await service.generate_copy(
            product_name=req.product_name,
            features=req.features,
            language=req.language,
            provider=req.provider,
            model=req.model,
            requested_by=user.email,
        )
    except AiContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/translate")
async def translate_product(
    req: TranslateRequest,
    user: AdminUserDep,
    gateway: GatewayDep,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AiContentService(gateway, db)
    try:
        return await service.translate(
            title=req.title,
            description=req.description,
            bullets=req.bullets,
            target_language=req.target_language,
            provider=req.provider,
            model=req.model,
            requested_by=user.email,
        )
    except AiContentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, _: AdminUserDep, gateway: GatewayDep) -> StreamingResponse:
    """流式输出（SSE），必须能正常结束（spec §43）。"""
    messages = []
    if req.system:
        messages.append(LLMMessage("system", req.system))
    messages.append(LLMMessage("user", req.prompt))

    async def event_source():
        try:
            async for piece in gateway.stream(messages, provider=req.provider, model=req.model):
                yield f"data: {piece}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        except LLMError as exc:
            yield f"event: error\ndata: {exc}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@router.get("/usage")
async def usage(_: AdminUserDep, db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=500)) -> dict:
    repo = UsageRepository(db)
    rows = await repo.list(limit=limit)
    return {
        "summary": await repo.summary(),
        "items": [
            {
                "id": r.id,
                "provider": r.provider,
                "model": r.model,
                "operation": r.operation,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "latency_ms": r.latency_ms,
                "requested_by": r.requested_by,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
