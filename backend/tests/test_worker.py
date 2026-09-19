import asyncio

import pytest

from app.worker.registry import REGISTRY
from app.worker.runner import run_task
from app.worker.tasks import ping  # noqa: F401


@pytest.mark.asyncio
async def test_ping_task_executes():
    result, attempts = await run_task(REGISTRY, "ping", {"hello": "world"})
    assert result["pong"] is True
    assert result["echo"] == {"hello": "world"}
    assert attempts == 1


@pytest.mark.asyncio
async def test_unknown_task_raises():
    with pytest.raises(KeyError):
        await run_task(REGISTRY, "no_such_task", {})


@pytest.mark.asyncio
async def test_task_timeout_is_enforced():
    async def slow(payload):
        await asyncio.sleep(1)
        return {"done": True}

    registry = {"slow": slow}
    with pytest.raises(asyncio.TimeoutError):
        await run_task(registry, "slow", {}, timeout=0.05)


@pytest.mark.asyncio
async def test_task_retries_then_succeeds():
    calls = {"n": 0}

    async def flaky(payload):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    result, attempts = await run_task({"flaky": flaky}, "flaky", {}, max_retries=3, retry_backoff=0.01)
    assert result == {"ok": True}
    assert attempts == 3


@pytest.mark.asyncio
async def test_task_fails_after_retries_exhausted():
    async def always_fail(payload):
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError):
        await run_task({"always_fail": always_fail}, "always_fail", {}, max_retries=2, retry_backoff=0.01)
