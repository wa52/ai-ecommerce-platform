import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.infrastructure.http.middleware import SECURITY_HEADERS
from app.infrastructure.http.ratelimit import RateLimiter
from app.main import create_app


def test_request_id_and_security_headers():
    client = TestClient(create_app())
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")
    assert resp.headers.get("X-Response-Time-ms") is not None
    for key, value in SECURITY_HEADERS.items():
        assert resp.headers.get(key) == value


def test_request_id_is_propagated_when_provided():
    client = TestClient(create_app())
    resp = client.get("/api/v1/health/live", headers={"X-Request-ID": "trace-abc-123"})
    assert resp.headers["X-Request-ID"] == "trace-abc-123"


def test_unhandled_exception_returns_safe_message():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient as TC

    from app.infrastructure.http.middleware import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("internal detail should not leak")

    resp = TC(app, raise_server_exceptions=False).get("/boom")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "服务器内部错误，请稍后重试"
    assert "internal detail" not in resp.text
    assert resp.json().get("request_id")


def test_openapi_generates():
    schema = create_app().openapi()
    assert schema["paths"]
    assert "/api/v1/analytics/overview" in schema["paths"]


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit(monkeypatch):
    limiter = RateLimiter(limit=2, window_seconds=60, prefix="test")

    class FakeRedis:
        def __init__(self):
            self.counts: dict[str, int] = {}

        async def incr(self, key):
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]

        async def expire(self, key, seconds):
            return True

    fake = FakeRedis()
    monkeypatch.setattr("app.infrastructure.http.ratelimit.get_redis", lambda: fake)

    allowed1, remaining1 = await limiter.check("ip-1")
    allowed2, _ = await limiter.check("ip-1")
    allowed3, remaining3 = await limiter.check("ip-1")
    assert allowed1 and allowed2
    assert allowed3 is False
    assert remaining3 == 0
    assert remaining1 == 1


@pytest.mark.asyncio
async def test_rate_limiter_fails_open_when_redis_down(monkeypatch):
    limiter = RateLimiter(limit=1, window_seconds=60, prefix="test-down")

    def broken():
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.infrastructure.http.ratelimit.get_redis", broken)
    allowed, remaining = await limiter.check("ip-x")
    assert allowed is True
    assert remaining == 1
