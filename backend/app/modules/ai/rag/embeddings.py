"""嵌入（Embedding）抽象（spec §16）。

- 生产环境可用 OpenAI 兼容的 embeddings 接口
- 无外部凭据时使用确定性的本地 Hashing Provider（Sandbox / 离线可用）
"""

import hashlib
import math
from abc import ABC, abstractmethod

import httpx

EMBEDDING_DIM = 1536


class EmbeddingError(Exception):
    pass


class EmbeddingProvider(ABC):
    name: str = "unknown"
    dim: int = EMBEDDING_DIM

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbeddingProvider(EmbeddingProvider):
    """确定性哈希嵌入：无外部依赖，适合 Sandbox 与单元测试。

    不用于生产语义检索质量要求；生产应配置真实 embedding 服务。
    """

    name = "hashing"

    def __init__(self, dim: int = EMBEDDING_DIM):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = [t for t in _tokenize(text) if t]
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    name = "openai_compatible"

    def __init__(self, *, base_url: str, api_key: str, model: str, dim: int = EMBEDDING_DIM, timeout: float = 30.0):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.dim = dim
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.configured:
            raise EmbeddingError("Embedding Provider 未配置（缺少 LLM_BASE_URL / LLM_API_KEY）")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"model": self.model, "input": texts},
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                raise EmbeddingError(f"Embedding 服务返回 {resp.status_code}")
            body = resp.json()
        data = body.get("data") or []
        if len(data) != len(texts):
            raise EmbeddingError("Embedding 服务返回数量不匹配")
        vectors = [item.get("embedding") for item in data]
        if any(not isinstance(v, list) for v in vectors):
            raise EmbeddingError("Embedding 服务返回格式异常")
        return vectors


def _tokenize(text: str) -> list[str]:
    """中英文混合的轻量分词（英文按空白，中文按字）。"""
    tokens: list[str] = []
    current: list[str] = []
    for ch in text.lower():
        if ch.isalnum() and ord(ch) < 128:
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
            if "\u4e00" <= ch <= "\u9fff":
                tokens.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(size))
    na = math.sqrt(sum(a[i] * a[i] for i in range(size))) or 1.0
    nb = math.sqrt(sum(b[i] * b[i] for i in range(size))) or 1.0
    return dot / (na * nb)


def build_embedding_provider(settings) -> EmbeddingProvider:
    provider = OpenAICompatibleEmbeddingProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.embedding_model,
    )
    if provider.configured and settings.embedding_provider == "openai_compatible":
        return provider
    return HashingEmbeddingProvider()
