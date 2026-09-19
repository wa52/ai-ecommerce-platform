"""AI 电商能力（spec §17）：商品文案生成与翻译。

所有调用必须经 LLMGateway，并记录 Token Usage。
"""

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.llm.base import LLMError, LLMMessage
from app.modules.ai.llm.gateway import LLMGateway
from app.modules.ai.llm.usage import UsageRepository

logger = logging.getLogger(__name__)

_COPY_SYSTEM = (
    "你是资深跨境电商运营。请基于给定商品信息撰写{language}文案。"
    "要求：标题不超过 200 字符；卖点 3-5 条；描述客观、无夸大、不得编造参数。"
    "只输出 JSON：{{\"title\": string, \"bullets\": string[], \"description\": string}}"
)

_TRANSLATE_SYSTEM = (
    "你是专业电商翻译。把商品信息翻译成{target_language}，保留数字与单位，"
    "只输出 JSON：{{\"title\": string, \"description\": string, \"bullets\": string[]}}"
)


class AiContentError(Exception):
    def __init__(self, message: str, *, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _parse_json(text: str) -> dict:
    import json

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise AiContentError("模型未返回可解析的 JSON")
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AiContentError("模型返回的 JSON 无法解析") from exc


class AiContentService:
    def __init__(self, gateway: LLMGateway, session: AsyncSession | None = None):
        self._gateway = gateway
        self._usage = UsageRepository(session) if session is not None else None

    async def _run(self, messages: list[LLMMessage], *, operation: str, requested_by: str | None,
                   provider: str | None, model: str | None, max_tokens: int) -> dict:
        started = time.monotonic()
        try:
            response = await self._gateway.complete(
                messages, provider=provider, model=model, max_tokens=max_tokens
            )
        except LLMError as exc:
            raise AiContentError(str(exc), status_code=exc.status_code) from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if self._usage is not None:
            await self._usage.record(
                provider=response.provider,
                model=response.model,
                operation=operation,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                latency_ms=latency_ms,
                requested_by=requested_by,
            )

        payload = _parse_json(response.content)
        payload["_meta"] = {
            "provider": response.provider,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "latency_ms": latency_ms,
        }
        return payload

    async def generate_copy(
        self,
        *,
        product_name: str,
        features: list[str] | None,
        language: str,
        provider: str | None = None,
        model: str | None = None,
        requested_by: str | None = None,
    ) -> dict:
        feature_text = "；".join(features or []) or "（无）"
        messages = [
            LLMMessage("system", _COPY_SYSTEM.format(language=language)),
            LLMMessage("user", f"商品名称：{product_name}\n已知卖点：{feature_text}"),
        ]
        return await self._run(
            messages, operation="product_copy", requested_by=requested_by,
            provider=provider, model=model, max_tokens=800,
        )

    async def translate(
        self,
        *,
        title: str,
        description: str | None,
        bullets: list[str] | None,
        target_language: str,
        provider: str | None = None,
        model: str | None = None,
        requested_by: str | None = None,
    ) -> dict:
        messages = [
            LLMMessage("system", _TRANSLATE_SYSTEM.format(target_language=target_language)),
            LLMMessage(
                "user",
                f"标题：{title}\n描述：{description or '（无）'}\n卖点：{'；'.join(bullets or []) or '（无）'}",
            ),
        ]
        return await self._run(
            messages, operation="translate", requested_by=requested_by,
            provider=provider, model=model, max_tokens=800,
        )
