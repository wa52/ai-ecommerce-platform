from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.repository.models import AiLlmUsage


class UsageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def record(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: int,
        requested_by: str | None,
    ) -> AiLlmUsage:
        row = AiLlmUsage(
            provider=provider,
            model=model,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            requested_by=requested_by,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def list(self, *, limit: int = 100) -> list[AiLlmUsage]:
        stmt = select(AiLlmUsage).order_by(AiLlmUsage.created_at.desc()).limit(limit)
        return list((await self._session.execute(stmt)).scalars())

    async def summary(self) -> dict:
        rows = await self.list(limit=1000)
        return {
            "calls": len(rows),
            "prompt_tokens": sum(r.prompt_tokens for r in rows),
            "completion_tokens": sum(r.completion_tokens for r in rows),
            "total_tokens": sum(r.total_tokens for r in rows),
        }
