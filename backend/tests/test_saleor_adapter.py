import httpx
import pytest

from app.connectors.saleor import SaleorAdapter


def _mock_resp(data: dict) -> httpx.Response:
    return httpx.Response(200, json=data, request=httpx.Request("POST", "http://test/graphql/"))


@pytest.mark.asyncio
async def test_saleor_health_ok():
    transport = httpx.MockTransport(lambda req: _mock_resp({"data": {"shop": {"id": "1"}}}))
    adapter = SaleorAdapter("http://test/graphql/", transport=transport)
    result = await adapter.health()
    assert result.ok is True
    assert "shop" in result.detail


@pytest.mark.asyncio
async def test_saleor_health_failure_is_reported_not_raised():
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    adapter = SaleorAdapter("http://test/graphql/", transport=transport)
    result = await adapter.health()
    assert result.ok is False
    assert "50" in result.detail or "Saleor" in result.detail


@pytest.mark.asyncio
async def test_saleor_graphql_errors_raise():
    transport = httpx.MockTransport(lambda req: _mock_resp({"errors": [{"message": "bad"}]}))
    adapter = SaleorAdapter("http://test/graphql/", transport=transport)
    with pytest.raises(RuntimeError):
        await adapter.graphql("{shop{id}}")


@pytest.mark.asyncio
async def test_connection_refused_not_ok():
    adapter = SaleorAdapter("http://127.0.0.1:59999/graphql/", timeout=1)
    result = await adapter.health()
    assert result.ok is False
