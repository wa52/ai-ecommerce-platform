import asyncio
import json
import logging
import signal
import sys
import time

from app.infrastructure.config.settings import get_settings
from app.infrastructure.logging.setup import setup_logging
from app.infrastructure.redis.client import get_redis
from app.worker import tasks  # noqa: F401  (ensure builtin tasks are registered)
from app.worker.registry import REGISTRY
from app.worker.runner import run_task

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging()
    r = get_redis()
    queue = settings.worker_queue

    logger.info("worker started, consuming queue: %s, tasks: %s", queue, sorted(REGISTRY))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    while not stop.is_set():
        try:
            item = await r.blpop(queue, timeout=2)
        except asyncio.CancelledError:
            break
        if item is None:
            continue
        _, raw = item
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("invalid task message: %r", raw[:200])
            continue

        task_id = message.get("id", "unknown")
        name = message.get("name", "")
        payload = message.get("payload", {})
        result_key = f"task:result:{task_id}"
        started = time.monotonic()
        try:
            result = await run_task(REGISTRY, name, payload)
            record = {
                "id": task_id,
                "task": name,
                "status": "success",
                "result": result,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "finished_at": time.time(),
            }
        except KeyError as exc:
            record = {
                "id": task_id,
                "task": name,
                "status": "failed",
                "error": str(exc),
                "finished_at": time.time(),
            }
        except Exception as exc:
            record = {
                "id": task_id,
                "task": name,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "finished_at": time.time(),
            }
        await r.set(result_key, json.dumps(record, ensure_ascii=False), ex=settings.worker_result_ttl)
        logger.info("task %s [%s] -> %s", task_id, name, record["status"])

    logger.info("worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
