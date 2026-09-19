import json
import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.infrastructure.config.settings import get_settings
from app.infrastructure.redis.client import get_redis

router = APIRouter(prefix="/tasks", tags=["worker"])


class TaskCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


class TaskCreateResponse(BaseModel):
    id: str
    name: str
    status: str = "queued"


class TaskStatusResponse(BaseModel):
    id: str
    task: str
    status: str
    result: dict | None = None
    error: str | None = None
    duration_ms: int | None = None


@router.post("", response_model=TaskCreateResponse, status_code=202)
async def create_task(req: TaskCreateRequest) -> TaskCreateResponse:
    settings = get_settings()
    task_id = uuid.uuid4().hex
    message = json.dumps({"id": task_id, "name": req.name, "payload": req.payload})
    try:
        await get_redis().lpush(settings.worker_queue, message)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail=f"任务队列不可用：{exc}") from exc
    return TaskCreateResponse(id=task_id, name=req.name)


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    raw = await get_redis().get(f"task:result:{task_id}")
    if raw is None:
        raise HTTPException(status_code=404, detail=f"任务不存在或未完成：{task_id}")
    record = json.loads(raw)
    return TaskStatusResponse(**record)


@router.get("", response_model=list[TaskStatusResponse])
async def list_recent_tasks(limit: int = Query(default=10, ge=1, le=100)) -> list[TaskStatusResponse]:
    settings = get_settings()
    r = get_redis()
    ids = await r.lrange("task:history", 0, limit - 1)
    results: list[TaskStatusResponse] = []
    for task_id in ids:
        raw = await r.get(f"task:result:{task_id}")
        if raw is not None:
            results.append(TaskStatusResponse(**json.loads(raw)))
    return results
