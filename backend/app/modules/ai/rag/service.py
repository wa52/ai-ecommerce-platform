"""RAG（spec §16）：切块 → 嵌入 → 混合检索（向量 + 关键词）→ 重排 → 上下文。

无证据时必须拒绝编造（spec §45）。
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.llm.base import LLMMessage
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.rag.embeddings import EmbeddingProvider, cosine
from app.modules.ai.rag.models import Document, DocumentChunk, KnowledgeBase

logger = logging.getLogger(__name__)

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
MIN_SCORE = 0.05
# 仅靠向量、且相似度低于该阈值时，视为不相关（防止非语义嵌入产生虚假命中）
STRONG_VECTOR_MIN = 0.5
# 中文单字重叠噪声大，关键词匹配使用中文双字（bigram）+ 英文词
MIN_KEYWORD_SCORE = 0.15


def keyword_units(text: str) -> set[str]:
    """关键词单元：英文/数字按词，中文按双字（单字文本回退为单字）。"""
    units: set[str] = set()
    word: list[str] = []
    cjk: list[str] = []

    def flush_word() -> None:
        if word:
            units.add("".join(word))
            word.clear()

    def flush_cjk() -> None:
        if len(cjk) == 1:
            units.add(cjk[0])
        else:
            for i in range(len(cjk) - 1):
                units.add(cjk[i] + cjk[i + 1])
        cjk.clear()

    for ch in text.lower():
        if ch.isalnum() and ord(ch) < 128:
            flush_cjk()
            word.append(ch)
        elif "\u4e00" <= ch <= "\u9fff":
            flush_word()
            cjk.append(ch)
        else:
            flush_word()
            flush_cjk()
    flush_word()
    flush_cjk()
    return units


class RagError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    source: str | None
    ordinal: int
    content: str
    vector_score: float
    keyword_score: float
    score: float

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "source": self.source,
            "ordinal": self.ordinal,
            "content": self.content,
            "vector_score": round(self.vector_score, 4),
            "keyword_score": round(self.keyword_score, 4),
            "score": round(self.score, 4),
        }


@dataclass
class RagAnswer:
    answer: str
    grounded: bool
    contexts: list[RetrievedChunk] = field(default_factory=list)
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "answer": self.answer,
            "grounded": self.grounded,
            "reason": self.reason,
            "contexts": [c.as_dict() for c in self.contexts],
        }


def split_into_chunks(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """按段落聚合切块，带重叠，避免跨段语义割裂。"""
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if not buffer:
            buffer = para
        elif len(buffer) + len(para) + 1 <= size:
            buffer = f"{buffer}\n{para}"
        else:
            chunks.append(buffer)
            tail = buffer[-overlap:] if overlap and len(buffer) > overlap else ""
            buffer = f"{tail}\n{para}".strip() if tail else para
        while len(buffer) > size * 2:
            chunks.append(buffer[:size])
            buffer = buffer[size - overlap :]
    if buffer:
        chunks.append(buffer)
    return [c for c in chunks if c.strip()]


class RagService:
    def __init__(self, session: AsyncSession, embedder: EmbeddingProvider, gateway: LLMGateway | None = None):
        self._session = session
        self._embedder = embedder
        self._gateway = gateway

    # ---------- knowledge base / documents ----------

    async def create_kb(self, *, name: str, slug: str, description: str | None) -> KnowledgeBase:
        existing = await self._session.scalar(select(KnowledgeBase).where(KnowledgeBase.slug == slug))
        if existing is not None:
            raise RagError(f"知识库 slug 已存在：{slug}", status_code=409)
        kb = KnowledgeBase(name=name, slug=slug, description=description)
        self._session.add(kb)
        await self._session.commit()
        await self._session.refresh(kb)
        return kb

    async def list_kbs(self) -> list[KnowledgeBase]:
        return list((await self._session.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))).scalars())

    async def get_kb(self, kb_id: str) -> KnowledgeBase:
        kb = await self._session.get(KnowledgeBase, kb_id)
        if kb is None:
            raise RagError(f"知识库不存在：{kb_id}", status_code=404)
        return kb

    async def ingest(self, *, kb_id: str, title: str, content: str, source: str | None) -> Document:
        await self.get_kb(kb_id)
        document = Document(knowledge_base_id=kb_id, title=title, content=content, source=source)
        self._session.add(document)
        await self._session.flush()

        pieces = split_into_chunks(content)
        if not pieces:
            raise RagError("文档内容为空，无法建立索引", status_code=422)
        vectors = await self._embedder.embed(pieces)
        for ordinal, (piece, vector) in enumerate(zip(pieces, vectors)):
            self._session.add(
                DocumentChunk(
                    document_id=document.id,
                    knowledge_base_id=kb_id,
                    ordinal=ordinal,
                    content=piece,
                    embedding=vector,
                )
            )
        await self._session.commit()
        await self._session.refresh(document)
        return document

    # ---------- retrieval ----------

    async def retrieve(
        self, *, kb_id: str, query: str, top_k: int = 5, min_score: float = MIN_SCORE
    ) -> list[RetrievedChunk]:
        await self.get_kb(kb_id)
        rows = (
            await self._session.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.knowledge_base_id == kb_id)
            )
        ).all()
        if not rows:
            return []

        query_vector = (await self._embedder.embed([query]))[0]
        query_units = keyword_units(query)

        scored: list[RetrievedChunk] = []
        for chunk, document in rows:
            vector_score = cosine(query_vector, list(chunk.embedding or []))
            chunk_units = keyword_units(chunk.content)
            overlap = len(query_units & chunk_units)
            keyword_score = overlap / (len(query_units) or 1)
            # 混合打分：向量为主，关键词为辅（spec §16 Hybrid Retrieval）
            score = 0.7 * vector_score + 0.3 * keyword_score
            if score < min_score:
                continue
            # 相关性门槛：无词面重叠时必须向量足够强，否则视为无证据（spec §45 不得编造）
            if keyword_score < MIN_KEYWORD_SCORE and vector_score < STRONG_VECTOR_MIN:
                continue
            scored.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    source=document.source,
                    ordinal=chunk.ordinal,
                    content=chunk.content,
                    vector_score=vector_score,
                    keyword_score=keyword_score,
                    score=score,
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    # ---------- answer ----------

    async def answer(self, *, kb_id: str, question: str, top_k: int = 5) -> RagAnswer:
        if self._gateway is None:
            raise RagError("RAG 回答需要 LLM Gateway", status_code=500)
        contexts = await self.retrieve(kb_id=kb_id, query=question, top_k=top_k)
        if not contexts:
            return RagAnswer(
                answer="知识库中没有找到与该问题相关的资料，无法回答。",
                grounded=False,
                reason="no_context",
            )

        context_text = "\n\n".join(
            f"[{idx + 1}] {c.document_title}（来源：{c.source or '未标注'}）\n{c.content}"
            for idx, c in enumerate(contexts)
        )
        messages = [
            LLMMessage(
                "system",
                "你是知识库问答助手。只能依据提供的资料回答，并标注引用编号（如 [1]）。"
                "资料不足时必须明确说明无法回答，禁止使用模型自身知识补充。",
            ),
            LLMMessage("user", f"资料：\n{context_text}\n\n问题：{question}"),
        ]
        response = await self._gateway.complete(messages, max_tokens=600)
        return RagAnswer(answer=response.content, grounded=True, contexts=contexts)
