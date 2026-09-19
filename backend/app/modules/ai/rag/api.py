from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.session import get_db
from app.modules.ai.api.routes import get_llm_gateway
from app.modules.ai.llm.base import LLMError
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.rag.embeddings import EmbeddingError, build_embedding_provider
from app.modules.ai.rag.service import RagError, RagService
from app.modules.iam.api.deps import AdminUserDep

router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag_service(
    db: AsyncSession = Depends(get_db), gateway: LLMGateway = Depends(get_llm_gateway)
) -> RagService:
    return RagService(db, build_embedding_provider(get_settings()), gateway)


RagDep = Annotated[RagService, Depends(get_rag_service)]


class KbCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9-]+$", max_length=120)
    description: str | None = None


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    source: str | None = Field(default=None, max_length=300)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class AnswerRequest(SearchRequest):
    pass


def _handle(exc: Exception) -> HTTPException:
    status_code = getattr(exc, "status_code", 400)
    return HTTPException(status_code=status_code, detail=str(exc))


@router.post("/knowledge-bases", status_code=201)
async def create_kb(req: KbCreate, _: AdminUserDep, service: RagDep) -> dict:
    try:
        kb = await service.create_kb(name=req.name, slug=req.slug, description=req.description)
    except RagError as exc:
        raise _handle(exc) from exc
    return {"id": kb.id, "name": kb.name, "slug": kb.slug, "description": kb.description}


@router.get("/knowledge-bases")
async def list_kbs(_: AdminUserDep, service: RagDep) -> list[dict]:
    return [
        {"id": kb.id, "name": kb.name, "slug": kb.slug, "description": kb.description}
        for kb in await service.list_kbs()
    ]


@router.post("/knowledge-bases/{kb_id}/documents", status_code=201)
async def ingest_document(kb_id: str, req: DocumentCreate, _: AdminUserDep, service: RagDep) -> dict:
    try:
        document = await service.ingest(kb_id=kb_id, title=req.title, content=req.content, source=req.source)
    except (RagError, EmbeddingError) as exc:
        raise _handle(exc) from exc
    return {"id": document.id, "title": document.title, "knowledge_base_id": document.knowledge_base_id}


@router.post("/knowledge-bases/{kb_id}/search")
async def search(kb_id: str, req: SearchRequest, _: AdminUserDep, service: RagDep) -> dict:
    try:
        chunks = await service.retrieve(kb_id=kb_id, query=req.query, top_k=req.top_k)
    except (RagError, EmbeddingError) as exc:
        raise _handle(exc) from exc
    return {"query": req.query, "count": len(chunks), "chunks": [c.as_dict() for c in chunks]}


@router.post("/knowledge-bases/{kb_id}/answer")
async def answer(kb_id: str, req: AnswerRequest, _: AdminUserDep, service: RagDep) -> dict:
    try:
        result = await service.answer(kb_id=kb_id, question=req.query, top_k=req.top_k)
    except (RagError, EmbeddingError) as exc:
        raise _handle(exc) from exc
    except LLMError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return result.as_dict()
