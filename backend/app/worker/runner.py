import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

TaskFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def task(name: str, registry: dict[str, TaskFunc]) -> Callable[[TaskFunc], TaskFunc]:
    def decorator(fn: TaskFunc) -> TaskFunc:
        registry[name] = fn
        return fn

    return decorator


async def run_task(registry: dict[str, TaskFunc], name: str, payload: dict[str, Any]) -> dict[str, Any]:
    fn = registry.get(name)
    if fn is None:
        raise KeyError(f"unknown task: {name}")
    started = time.monotonic()
    try:
        result = await fn(payload)
    except Exception as exc:
        logger.exception("task %s failed", name)
        raise
    logger.info("task %s done in %.3fs", name, time.monotonic() - started)
    return result
