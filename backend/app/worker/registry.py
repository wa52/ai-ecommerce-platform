from collections.abc import Awaitable, Callable
from typing import Any

TaskFunc = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

REGISTRY: dict[str, TaskFunc] = {}
