import asyncio
from typing import Any

from app.worker.registry import REGISTRY


async def ping(payload: dict[str, Any]) -> dict[str, Any]:
    await asyncio.sleep(0)
    return {"pong": True, "echo": payload}


REGISTRY["ping"] = ping
