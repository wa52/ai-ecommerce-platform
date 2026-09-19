import asyncio
import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.modules.ai.llm.base import LLMError, LLMMessage, LLMProvider, LLMResponse, LLMUsage

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 Provider（OpenAI / DeepSeek / Qwen 等）。"""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: list[LLMMessage], model: str, temperature: float, max_tokens: int, stream: bool) -> dict:
        return {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    async def _post(self, payload: dict, *, stream: bool) -> httpx.Response:
        if not self.configured:
            raise LLMError("LLM Provider 未配置（缺少 LLM_BASE_URL / LLM_API_KEY）", status_code=503)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                client = httpx.AsyncClient(timeout=self.timeout, transport=self._transport)
                try:
                    if stream:
                        req = client.build_request("POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers())
                        response = await client.send(req, stream=True)
                    else:
                        response = await client.post(
                            f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
                        )
                except httpx.TimeoutException as exc:
                    last_error = exc
                    await client.aclose()
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.2 * (attempt + 1))
                        continue
                    raise LLMError("LLM 请求超时", status_code=504, retryable=True) from exc
                except httpx.HTTPError as exc:
                    await client.aclose()
                    raise LLMError(f"LLM 网络错误：{type(exc).__name__}", status_code=502) from exc

                if response.status_code in RETRYABLE_STATUS:
                    await response.aclose()
                    await client.aclose()
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.2 * (attempt + 1))
                        continue
                    raise LLMError(
                        f"LLM Provider 返回 {response.status_code}（重试 {self.max_retries} 次后仍失败）",
                        status_code=502 if response.status_code != 429 else 429,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    body = (await response.aread()).decode(errors="replace")[:200] if not stream else ""
                    await client.aclose()
                    raise LLMError(f"LLM Provider 错误 {response.status_code}: {body}", status_code=502)
                return response
            except LLMError:
                raise
        raise LLMError(f"LLM 调用失败：{last_error}", status_code=502)

    async def complete(
        self, messages: list[LLMMessage], *, model: str, temperature: float = 0.7, max_tokens: int = 1024
    ) -> LLMResponse:
        response = await self._post(
            self._payload(messages, model, temperature, max_tokens, stream=False), stream=False
        )
        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            raise LLMError("LLM 返回了非 JSON 响应", status_code=502) from exc
        finally:
            await response.aclose()

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMError("LLM 返回格式异常：缺少 choices", status_code=502)
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMError("LLM 返回格式异常：缺少 message.content", status_code=502)

        raw_usage = body.get("usage") or {}
        return LLMResponse(
            content=content,
            model=body.get("model") or model,
            provider=self.name,
            finish_reason=choices[0].get("finish_reason"),
            usage=LLMUsage(
                prompt_tokens=int(raw_usage.get("prompt_tokens") or 0),
                completion_tokens=int(raw_usage.get("completion_tokens") or 0),
                total_tokens=int(raw_usage.get("total_tokens") or 0),
            ),
        )

    async def stream(
        self, messages: list[LLMMessage], *, model: str, temperature: float = 0.7, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        response = await self._post(
            self._payload(messages, model, temperature, max_tokens, stream=True), stream=True
        )
        try:
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece
        finally:
            await response.aclose()
