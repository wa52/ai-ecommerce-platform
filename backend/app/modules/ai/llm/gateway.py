import logging
from collections.abc import AsyncIterator

from app.modules.ai.llm.base import LLMError, LLMMessage, LLMProvider, LLMResponse
from app.modules.ai.llm.providers import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


def redact(text: str, secret: str) -> str:
    """日志脱敏：任何情况下不得输出密钥（spec §43）。"""
    if not secret:
        return text
    return text.replace(secret, "***REDACTED***")


class LLMGateway:
    """统一模型调用入口（spec §14）。

    - 业务模块不得绕过本网关直接调用 Provider
    - 统一超时/重试/错误映射
    - 记录 Token Usage
    - 日志脱敏
    """

    def __init__(self, providers: dict[str, LLMProvider], *, default_provider: str, model: str):
        if default_provider not in providers:
            raise LLMError(f"未知的 LLM Provider：{default_provider}", status_code=500)
        self._providers = providers
        self._default_provider = default_provider
        self._model = model

    def list_providers(self) -> list[dict]:
        return [
            {"name": name, "configured": getattr(p, "configured", True)}
            for name, p in self._providers.items()
        ]

    def provider(self, name: str | None = None) -> LLMProvider:
        key = name or self._default_provider
        provider = self._providers.get(key)
        if provider is None:
            raise LLMError(f"未知的 LLM Provider：{key}", status_code=400)
        return provider

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        target = self.provider(provider)
        secret = getattr(target, "api_key", "")
        try:
            response = await target.complete(
                messages, model=model or self._model, temperature=temperature, max_tokens=max_tokens
            )
        except LLMError as exc:
            logger.warning("LLM call failed via %s: %s", target.name, redact(str(exc), secret))
            raise
        logger.info(
            "LLM call ok provider=%s model=%s tokens=%s",
            response.provider,
            response.model,
            response.usage.total_tokens,
        )
        return response

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        target = self.provider(provider)
        async for chunk in target.stream(
            messages, model=model or self._model, temperature=temperature, max_tokens=max_tokens
        ):
            yield chunk


def build_gateway(settings) -> LLMGateway:
    provider = OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
    return LLMGateway({provider.name: provider}, default_provider=settings.llm_provider, model=settings.llm_model)
