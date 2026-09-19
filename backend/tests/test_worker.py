import pytest

from app.worker.registry import REGISTRY
from app.worker.runner import run_task
from app.worker.tasks import ping  # noqa: F401


@pytest.mark.asyncio
async def test_ping_task_executes():
    result = await run_task(REGISTRY, "ping", {"hello": "world"})
    assert result["pong"] is True
    assert result["echo"] == {"hello": "world"}


@pytest.mark.asyncio
async def test_unknown_task_raises():
    with pytest.raises(KeyError):
        await run_task(REGISTRY, "no_such_task", {})
