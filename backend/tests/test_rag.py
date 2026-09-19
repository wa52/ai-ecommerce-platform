import pytest
from fastapi.testclient import TestClient

from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.ai.api.routes import get_llm_gateway
from app.modules.ai.llm.base import LLMProvider, LLMResponse
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.rag.api import get_rag_service
from app.modules.ai.rag.embeddings import HashingEmbeddingProvider, build_embedding_provider, cosine, _tokenize
from app.modules.ai.rag.service import RagError, RagService, split_into_chunks
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)

DOCS = [
    (
        "退货政策",
        "标准退货窗口为 30 天。\n\n买家需保持商品与包装完好，并附上订单号。\n\n生鲜类商品不支持无理由退货。",
        "handbook/returns.md",
    ),
    (
        "物流时效",
        "美国本土订单通常 3-5 个工作日送达。\n\n跨境订单需要 7-15 个工作日，并可能产生关税。\n\n旺季（11-12 月）时效会延长。",
        "handbook/shipping.md",
    ),
    (
        "支付与退款",
        "支持信用卡与 PayPal。\n\n退款在审核通过后 5 个工作日内原路退回。\n\n部分退款按剩余可退额度计算。",
        "handbook/payments.md",
    ),
]


class _NoopProvider(LLMProvider):
    name = "stub"

    async def complete(self, messages, *, model, temperature=0.7, max_tokens=1024, tools=None):
        return LLMResponse(content="", model=model, provider=self.name)

    async def stream(self, messages, *, model, temperature=0.7, max_tokens=1024):
        if False:  # pragma: no cover
            yield ""


class EchoGateway(LLMGateway):
    """把收到的上下文原样回显，便于断言"回答基于检索到的资料"。"""

    def __init__(self, content: str = "根据资料 [1] 回答。"):
        super().__init__({"stub": _NoopProvider()}, default_provider="stub", model="stub")
        self._content = content
        self.last_prompt = ""

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        self.last_prompt = "\n".join(m.content for m in messages)
        return LLMResponse(content=self._content, model="stub", provider="stub")


@pytest.fixture
async def rag(db_session_factory):
    gateway = EchoGateway()
    service = RagService(db_session_factory and await _session(db_session_factory), HashingEmbeddingProvider(), gateway)
    return service, gateway


async def _session(factory):
    return factory()


# ---------- chunking & embeddings ----------


def test_split_into_chunks_respects_paragraphs_and_size():
    text = "A" * 400 + "\n\n" + "B" * 100
    chunks = split_into_chunks(text, size=300, overlap=50)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)


def test_tokenize_handles_chinese_and_english():
    tokens = _tokenize("退货 window 30天")
    assert "window" in tokens
    assert "退" in tokens
    assert "货" in tokens
    assert "30" in tokens


@pytest.mark.asyncio
async def test_hashing_embedding_is_deterministic_and_normalized():
    provider = HashingEmbeddingProvider(dim=64)
    a = (await provider.embed(["退货政策 30 天"]))[0]
    b = (await provider.embed(["退货政策 30 天"]))[0]
    assert a == b
    assert abs(sum(v * v for v in a) ** 0.5 - 1.0) < 1e-6
    assert cosine(a, b) > 0.99


def test_build_embedding_provider_falls_back_to_hashing():
    class _Settings:
        llm_base_url = ""
        llm_api_key = ""
        embedding_provider = "openai_compatible"
        embedding_model = "x"

    provider = build_embedding_provider(_Settings())
    assert provider.name == "hashing"


# ---------- service: ingest + retrieve + answer ----------


@pytest.mark.asyncio
async def test_ingest_retrieve_and_hybrid_scores(db_session_factory):
    async with db_session_factory() as session:
        gateway = EchoGateway()
        service = RagService(session, HashingEmbeddingProvider(), gateway)
        kb = await service.create_kb(name="运营手册", slug="ops-handbook", description="d")
        for title, content, source in DOCS:
            await service.ingest(kb_id=kb.id, title=title, content=content, source=source)

        # 明确命中
        hits = await service.retrieve(kb_id=kb.id, query="退货窗口多少天", top_k=3)
        assert hits and hits[0].document_title == "退货政策"
        assert hits[0].vector_score > 0 and hits[0].keyword_score > 0
        assert hits[0].score == pytest.approx(0.7 * hits[0].vector_score + 0.3 * hits[0].keyword_score, rel=1e-6)

        # 同义表达（用不同措辞仍命中退款主题）
        synonyms = await service.retrieve(kb_id=kb.id, query="钱多久能退回来", top_k=3)
        assert any("退款" in h.content or "退款" in h.document_title for h in synonyms)

        # 多文档召回
        multi = await service.retrieve(kb_id=kb.id, query="物流 时效 关税", top_k=3)
        assert any(h.document_title == "物流时效" for h in multi)


@pytest.mark.asyncio
async def test_no_relevant_document_refuses_to_answer(db_session_factory):
    async with db_session_factory() as session:
        gateway = EchoGateway()
        service = RagService(session, HashingEmbeddingProvider(), gateway)
        kb = await service.create_kb(name="KB", slug="kb-empty-rel", description=None)
        await service.ingest(kb_id=kb.id, title="退货政策", content="标准退货窗口为 30 天。", source=None)

        result = await service.answer(kb_id=kb.id, question="量子计算机的退相干时间是多少")
        assert result.grounded is False
        assert result.reason == "no_context"
        assert "无法回答" in result.answer
        assert result.contexts == []
        assert gateway.last_prompt == ""  # 无证据时不得调用模型编造


@pytest.mark.asyncio
async def test_answer_includes_contexts_and_citations(db_session_factory):
    async with db_session_factory() as session:
        gateway = EchoGateway("依据资料 [1]，退货窗口为 30 天。")
        service = RagService(session, HashingEmbeddingProvider(), gateway)
        kb = await service.create_kb(name="KB2", slug="kb-cite", description=None)
        await service.ingest(kb_id=kb.id, title="退货政策", content="标准退货窗口为 30 天。", source="handbook/returns.md")

        result = await service.answer(kb_id=kb.id, question="退货窗口是多久")
        assert result.grounded is True
        assert result.contexts and result.contexts[0].document_title == "退货政策"
        assert "退货政策" in gateway.last_prompt  # 上下文真的传给了模型
        assert "handbook/returns.md" in gateway.last_prompt


@pytest.mark.asyncio
async def test_duplicate_kb_slug_rejected(db_session_factory):
    async with db_session_factory() as session:
        service = RagService(session, HashingEmbeddingProvider())
        await service.create_kb(name="A", slug="dup-slug", description=None)
        with pytest.raises(RagError):
            await service.create_kb(name="B", slug="dup-slug", description=None)


# ---------- API ----------


def _client(db_session_factory, gateway: LLMGateway) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_llm_gateway] = lambda: gateway

    async def override_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_rag_service] = lambda: RagService(
        _SyncSessionProxy(db_session_factory), HashingEmbeddingProvider(), gateway
    )
    return TestClient(app)


class _SyncSessionProxy:
    """让 TestClient（同步）也能拿到会话：每次操作新建会话。"""

    def __init__(self, factory):
        self._factory = factory

    def __getattr__(self, item):
        raise RuntimeError("should be replaced in tests")


def test_rag_api_flow(db_session_factory):
    gateway = EchoGateway("根据资料 [1]，窗口是 30 天。")

    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_llm_gateway] = lambda: gateway

    async def override_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    created = client.post(
        "/api/v1/rag/knowledge-bases", json={"name": "手册", "slug": "api-handbook"}
    )
    assert created.status_code == 201
    kb_id = created.json()["id"]

    doc = client.post(
        f"/api/v1/rag/knowledge-bases/{kb_id}/documents",
        json={"title": "退货政策", "content": "标准退货窗口为 30 天。", "source": "returns.md"},
    )
    assert doc.status_code == 201

    search = client.post(f"/api/v1/rag/knowledge-bases/{kb_id}/search", json={"query": "退货 30 天"})
    assert search.status_code == 200
    body = search.json()
    assert body["count"] >= 1
    chunk = body["chunks"][0]
    assert chunk["document_title"] == "退货政策"
    assert "score" in chunk and "vector_score" in chunk and "keyword_score" in chunk
    assert chunk["source"] == "returns.md"

    answer = client.post(f"/api/v1/rag/knowledge-bases/{kb_id}/answer", json={"query": "退货窗口"})
    assert answer.status_code == 200
    assert answer.json()["grounded"] is True
    assert answer.json()["contexts"]

    missing = client.post("/api/v1/rag/knowledge-bases/nope/search", json={"query": "x"})
    assert missing.status_code == 404


def test_rag_requires_admin(db_session_factory):
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"

    async def customer():
        return CurrentUser(id="U2", email="buyer@example.com", is_staff=False)

    app.dependency_overrides[get_current_user] = customer
    client = TestClient(app)
    assert client.get("/api/v1/rag/knowledge-bases").status_code == 403


# ---------- agent tool ----------


@pytest.mark.asyncio
async def test_rag_search_tool_registered_and_handles_missing_args():
    from app.modules.ai.tools.base import ToolContext
    from app.modules.ai.tools.registry import get_tool

    tool = get_tool("rag.search")
    assert tool is not None
    result = await tool.run(ToolContext(user=ADMIN), {})
    assert result.ok is False
    assert "缺少参数" in (result.error or "")


def test_rag_search_tool_is_agent_capability():
    from app.modules.ai.agent.runtime import build_registry

    ops = next(a for a in build_registry().list() if a["name"] == "operations")
    assert "rag.search" in ops["tools"]
