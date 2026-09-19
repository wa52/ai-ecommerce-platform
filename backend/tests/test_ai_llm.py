import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.ai.api.routes import get_llm_gateway
from app.modules.ai.application.content import AiContentError, AiContentService
from app.modules.ai.llm.base import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMUsage
from app.modules.ai.llm.gateway import LLMGateway, redact
from app.modules.ai.llm.providers import OpenAICompatibleProvider
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)
SECRET = "sk-super-secret-key"


def _ok_body(content: str) -> dict:
    return {
        "model": "fake-model",
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def _provider(handler, **kwargs) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="https://llm.example.com/v1",
        api_key=SECRET,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


# ---------- provider behaviours ----------


@pytest.mark.asyncio
async def test_provider_success_and_usage():
    provider = _provider(lambda req: httpx.Response(200, json=_ok_body('{"title":"x"}')))
    resp = await provider.complete([LLMMessage("user", "hi")], model="m")
    assert resp.content == '{"title":"x"}'
    assert resp.usage.total_tokens == 30
    assert resp.provider == "openai_compatible"


@pytest.mark.asyncio
async def test_provider_timeout_is_mapped():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    provider = _provider(handler, max_retries=0)
    with pytest.raises(LLMError, match="超时"):
        await provider.complete([LLMMessage("user", "hi")], model="m")


@pytest.mark.asyncio
async def test_provider_rate_limit_retries_then_fails():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": "rate limited"})

    provider = _provider(handler, max_retries=2)
    with pytest.raises(LLMError) as exc:
        await provider.complete([LLMMessage("user", "hi")], model="m")
    assert calls["n"] == 3  # 1 + 2 retries
    assert "429" in str(exc.value)


@pytest.mark.asyncio
async def test_provider_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json=_ok_body("ok"))

    provider = _provider(handler, max_retries=2)
    resp = await provider.complete([LLMMessage("user", "hi")], model="m")
    assert resp.content == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_provider_error_status_is_mapped():
    provider = _provider(lambda req: httpx.Response(400, json={"error": "bad request"}))
    with pytest.raises(LLMError, match="400"):
        await provider.complete([LLMMessage("user", "hi")], model="m")


@pytest.mark.asyncio
async def test_provider_malformed_payload_does_not_crash():
    provider = _provider(lambda req: httpx.Response(200, text="not-json"))
    with pytest.raises(LLMError, match="非 JSON"):
        await provider.complete([LLMMessage("user", "hi")], model="m")

    provider2 = _provider(lambda req: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(LLMError, match="choices"):
        await provider2.complete([LLMMessage("user", "hi")], model="m")

    provider3 = _provider(lambda req: httpx.Response(200, json={"choices": [{}]}))
    with pytest.raises(LLMError, match="content"):
        await provider3.complete([LLMMessage("user", "hi")], model="m")


@pytest.mark.asyncio
async def test_provider_unconfigured_is_503():
    provider = OpenAICompatibleProvider(base_url="", api_key="")
    assert provider.configured is False
    with pytest.raises(LLMError) as exc:
        await provider.complete([LLMMessage("user", "hi")], model="m")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_provider_stream_terminates():
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"好"}}]}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=body, headers={"Content-Type": "text/event-stream"})

    provider = _provider(handler)
    chunks = [c async for c in provider.stream([LLMMessage("user", "hi")], model="m")]
    assert "".join(chunks) == "你好"


# ---------- gateway ----------


def test_gateway_redacts_secret_in_logs():
    assert redact(f"call failed with {SECRET}", SECRET) == "call failed with ***REDACTED***"
    assert SECRET not in redact(f"Authorization: Bearer {SECRET}", SECRET)


@pytest.mark.asyncio
async def test_gateway_provider_switch_and_unknown_provider():
    a = _provider(lambda req: httpx.Response(200, json=_ok_body("A")))
    a.name = "provider_a"
    b = _provider(lambda req: httpx.Response(200, json=_ok_body("B")))
    b.name = "provider_b"
    gateway = LLMGateway({"provider_a": a, "provider_b": b}, default_provider="provider_a", model="m")

    assert (await gateway.complete([LLMMessage("user", "x")])).content == "A"
    assert (await gateway.complete([LLMMessage("user", "x")], provider="provider_b")).content == "B"
    with pytest.raises(LLMError):
        await gateway.complete([LLMMessage("user", "x")], provider="nope")


def test_gateway_rejects_unknown_default_provider():
    with pytest.raises(LLMError):
        LLMGateway({}, default_provider="missing", model="m")


# ---------- content service ----------


class _NoopProvider(LLMProvider):
    name = "stub"

    async def complete(self, messages, *, model, temperature=0.7, max_tokens=1024):
        return LLMResponse(content="", model=model, provider=self.name)

    async def stream(self, messages, *, model, temperature=0.7, max_tokens=1024):
        if False:  # pragma: no cover
            yield ""


class _StubGateway(LLMGateway):
    def __init__(self, content: str):
        super().__init__({"stub": _NoopProvider()}, default_provider="stub", model="m")
        self._content = content

    async def complete(self, messages, **kwargs):  # type: ignore[override]
        return LLMResponse(content=self._content, model="m", provider="stub", usage=LLMUsage(1, 2, 3))


@pytest.mark.asyncio
async def test_generate_copy_parses_json_and_reports_usage():
    gateway = _StubGateway('{"title":"T","bullets":["a","b"],"description":"D"}')
    service = AiContentService(gateway)
    result = await service.generate_copy(product_name="杯子", features=["陶瓷"], language="英文")
    assert result["title"] == "T"
    assert result["bullets"] == ["a", "b"]
    assert result["_meta"]["usage"]["total_tokens"] == 3


@pytest.mark.asyncio
async def test_generate_copy_handles_code_fence_and_bad_json():
    fenced = _StubGateway('```json\n{"title":"T","bullets":[],"description":"D"}\n```')
    assert (await AiContentService(fenced).generate_copy(
        product_name="x", features=[], language="中文"))["title"] == "T"

    broken = _StubGateway("sorry, no json here")
    with pytest.raises(AiContentError):
        await AiContentService(broken).generate_copy(product_name="x", features=[], language="中文")


@pytest.mark.asyncio
async def test_translate_parses_json():
    gateway = _StubGateway('{"title":"Hello","description":"Desc","bullets":["b"]}')
    result = await AiContentService(gateway).translate(
        title="你好", description="描述", bullets=["卖点"], target_language="英语"
    )
    assert result["title"] == "Hello"


# ---------- API ----------


def _client(db_session_factory, gateway: LLMGateway | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    if gateway is not None:
        app.dependency_overrides[get_llm_gateway] = lambda: gateway

    async def override_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_ai_endpoints_require_admin():
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"

    async def customer():
        return CurrentUser(id="U2", email="buyer@example.com", is_staff=False)

    app.dependency_overrides[get_current_user] = customer
    assert TestClient(app).post("/api/v1/ai/copy/product", json={"product_name": "x"}).status_code == 403


def test_copy_endpoint_records_usage(db_session_factory):
    gateway = _StubGateway('{"title":"T","bullets":[],"description":"D"}')
    client = _client(db_session_factory, gateway)

    resp = client.post("/api/v1/ai/copy/product", json={"product_name": "杯子", "language": "英文"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "T"

    usage = client.get("/api/v1/ai/usage").json()
    assert usage["summary"]["calls"] >= 1
    assert usage["summary"]["total_tokens"] >= 3
    assert usage["items"][0]["operation"] == "product_copy"
    assert usage["items"][0]["requested_by"] == "admin@example.com"


def test_providers_endpoint_lists_provider():
    client = _client(None) if False else None
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    providers = TestClient(app).get("/api/v1/ai/providers").json()
    assert providers[0]["name"] == "openai_compatible"


def test_copy_endpoint_maps_llm_error(db_session_factory):
    class _FailingGateway(LLMGateway):
        def __init__(self):
            super().__init__({"stub": _NoopProvider()}, default_provider="stub", model="m")

        async def complete(self, messages, **kwargs):  # type: ignore[override]
            raise LLMError("LLM Provider 未配置", status_code=503)

    client = _client(db_session_factory, _FailingGateway())
    resp = client.post("/api/v1/ai/copy/product", json={"product_name": "x"})
    assert resp.status_code == 503


def test_chat_stream_terminates_with_done(db_session_factory):
    class _StreamingGateway(LLMGateway):
        def __init__(self):
            super().__init__({"stub": _NoopProvider()}, default_provider="stub", model="m")

        async def stream(self, messages, **kwargs):  # type: ignore[override]
            for piece in ("你", "好"):
                yield piece

    client = _client(db_session_factory, _StreamingGateway())
    with client.stream("POST", "/api/v1/ai/chat/stream", json={"prompt": "hi"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert "data: 你" in body
    assert "data: 好" in body
    assert "event: done" in body
    assert "[DONE]" in body
