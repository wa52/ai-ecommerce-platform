import logging

import httpx

from app.connectors.base import CommerceAdapter, CommerceHealth

logger = logging.getLogger(__name__)

_SHOP_QUERY = "{shop{id}}"


class SaleorAdapter(CommerceAdapter):
    def __init__(self, api_url: str, timeout: float = 5.0, transport: httpx.AsyncBaseTransport | None = None):
        self.api_url = api_url
        self.timeout = timeout
        self._transport = transport

    async def graphql(self, query: str, variables: dict | None = None, token: str | None = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
            resp = await client.post(
                self.api_url,
                json={"query": query, "variables": variables or {}},
                headers=headers,
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Saleor HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"Saleor GraphQL errors: {data['errors']}")
        return data.get("data", {})

    async def health(self) -> CommerceHealth:
        try:
            data = await self.graphql(_SHOP_QUERY)
            shop_id = data.get("shop", {}).get("id")
            return CommerceHealth(True, f"shop id={shop_id}")
        except Exception as exc:
            logger.warning("saleor health check failed: %s", exc)
            return CommerceHealth(
                False,
                f"无法连接 Saleor API（{self.api_url}）：{type(exc).__name__}: {exc}",
            )
