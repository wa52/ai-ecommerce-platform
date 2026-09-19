import asyncio
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


async def run_task(
    registry: dict[str, TaskFunc],
    name: str,
    payload: dict[str, Any],
    *,
    timeout: float = 60.0,
    max_retries: int = 0,
    retry_backoff: float = 0.5,
) -> tuple[dict[str, Any], int]:
    """执行任务：带超时与重试。

    返回 (结果, 实际尝试次数)。超时/异常在重试耗尽后抛出。
    """
    fn = registry.get(name)
    if fn is None:
        raise KeyError(f"unknown task: {name}")

    started = time.monotonic()
    attempts = 0
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        try:
            result = await asyncio.wait_for(fn(payload), timeout=timeout)
            logger.info(
                "task %s done in %.3fs (attempt %d)", name, time.monotonic() - started, attempts
            )
            return result, attempts
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning("task %s timed out after %.1fs (attempt %d)", name, timeout, attempts)
        except Exception as exc:  # noqa: BLE001 - 需重试或上报
            last_error = exc
            logger.warning("task %s failed: %s (attempt %d)", name, type(exc).__name__, attempts)
        if attempt < max_retries:
            await asyncio.sleep(retry_backoff * (attempt + 1))

    assert last_error is not None
    raise last_error
