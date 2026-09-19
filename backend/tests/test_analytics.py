from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.connectors.base import CommerceAdapter, CommerceHealth
from app.connectors.factory import get_commerce_adapter
from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.analytics.domain.formulas import FORMULAS, MetricInputs, compute_metrics, sum_money
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)


# ---------- 公式（spec §42 要求人工可核对） ----------


def test_formulas_are_documented():
    for key in (
        "gmv",
        "net_sales",
        "order_count",
        "avg_order_value",
        "refund_rate",
        "platform_fee",
        "payment_fee",
        "net_settled",
        "profit",
        "profit_margin",
    ):
        assert key in FORMULAS and FORMULAS[key].strip()


def test_metrics_match_spec_example():
    """spec §42 示例：收入 1000 / 退款 100 / 平台费 50 / 支付费 20 / 其他成本 200 → 利润 630。"""
    metrics = compute_metrics(
        MetricInputs(
            gmv=Decimal("1000.00"),
            refund_total=Decimal("100.00"),
            order_count=10,
            platform_fee=Decimal("50.00"),
            payment_fee=Decimal("20.00"),
            net_settled=Decimal("930.00"),
            currency="USD",
            other_cost=Decimal("200.00"),
        )
    )
    assert metrics["gmv"] == "1000.00"
    assert metrics["net_sales"] == "900.00"
    assert metrics["order_count"] == "10"
    assert metrics["avg_order_value"] == "100.00"
    assert metrics["refund_rate_percent"] == "10.00"
    assert metrics["profit"] == "630.00"
    assert metrics["profit_margin_percent"] == "70.00"


def test_metrics_handle_zero_division_safely():
    metrics = compute_metrics(
        MetricInputs(
            gmv=Decimal("0"),
            refund_total=Decimal("0"),
            order_count=0,
            platform_fee=Decimal("0"),
            payment_fee=Decimal("0"),
            net_settled=Decimal("0"),
            currency="USD",
        )
    )
    assert metrics["avg_order_value"] == "0.00"
    assert metrics["refund_rate_percent"] == "0.00"
    assert metrics["profit_margin_percent"] == "0.00"


def test_metrics_respect_currency_precision():
    metrics = compute_metrics(
        MetricInputs(
            gmv=Decimal("1000"),
            refund_total=Decimal("0"),
            order_count=3,
            platform_fee=Decimal("0"),
            payment_fee=Decimal("0"),
            net_settled=Decimal("1000"),
            currency="JPY",
        )
    )
    assert metrics["avg_order_value"] == "333"  # JPY 无小数位，half-up


def test_sum_money_uses_decimal():
    assert sum_money([Decimal("0.1"), Decimal("0.2")], "USD") == Decimal("0.30")


# ---------- API ----------


class FakeCommerce(CommerceAdapter):
    def __init__(self, orders: list[dict]):
        self._orders = orders

    async def health(self) -> CommerceHealth:
        return CommerceHealth(True, "fake")

    async def graphql(self, query: str, variables: dict | None = None, token: str | None = None) -> dict:
        if "query Orders" in query:
            return {
                "orders": {
                    "totalCount": len(self._orders),
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "edges": [
                        {
                            "node": {
                                "id": f"O{i}",
                                "number": o["number"],
                                "status": o.get("status", "UNFULFILLED"),
                                "paymentStatus": "PAID",
                                "created": o["created"],
                                "channel": {"slug": "default-channel"},
                                "total": {"gross": {"amount": o["amount"], "currency": o["currency"]}},
                                "lines": [],
                            }
                        }
                        for i, o in enumerate(self._orders)
                    ],
                }
            }
        if "query Channels" in query:
            return {"channels": [{"id": "C1", "name": "D", "slug": "default-channel", "currencyCode": "USD", "isActive": True, "defaultCountry": {"code": "US"}}]}
        raise AssertionError(f"unexpected query: {query[:60]}")


def _client(db_session_factory, orders: list[dict]) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    app.dependency_overrides[get_commerce_adapter] = lambda: FakeCommerce(orders)

    async def override_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_overview_computes_metrics_from_real_records(db_session_factory):
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    orders = [
        {"number": "1", "amount": "600.00", "currency": "USD", "created": now},
        {"number": "2", "amount": "400.00", "currency": "USD", "created": now},
        {"number": "3", "amount": "1000", "currency": "JPY", "created": now},
    ]
    client = _client(db_session_factory, orders)

    # 造一笔 USD 退款与结算，验证与订单一起参与口径计算
    payment = client.post(
        "/api/v1/finance/payments",
        json={"order_ref": "1", "provider": "stripe", "amount": "1000.00", "currency": "USD", "idempotency_key": "an-1"},
    )
    assert payment.status_code == 201
    refund = client.post(
        "/api/v1/finance/refunds",
        json={"payment_id": payment.json()["id"], "amount": "100.00", "idempotency_key": "an-r1"},
    )
    assert refund.status_code == 201
    settlement = client.post(
        "/api/v1/finance/settlements",
        json={
            "platform": "shopify",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "currency": "USD",
            "platform_fee_rate": "5",
            "payment_fee_rate": "2",
            "items": [{"order_ref": "1", "gross_amount": "1000.00"}],
        },
    )
    assert settlement.status_code == 201

    resp = client.get("/api/v1/analytics/overview?days=30&other_cost=200.00")
    assert resp.status_code == 200
    body = resp.json()
    usd = body["by_currency"]["USD"]

    # 人工核算：GMV=1000.00；退款=100.00；销售额=900.00
    # 平台费=50.00；支付费=20.00；其他成本=200.00 → 利润=630.00；利润率=70.00%
    assert usd["gmv"] == "1000.00"
    assert usd["refund_total"] == "100.00"
    assert usd["net_sales"] == "900.00"
    assert usd["order_count"] == "2"
    assert usd["avg_order_value"] == "500.00"
    assert usd["refund_rate_percent"] == "10.00"
    assert usd["platform_fee"] == "50.00"
    assert usd["payment_fee"] == "20.00"
    assert usd["net_settled"] == "930.00"
    assert usd["profit"] == "630.00"
    assert usd["profit_margin_percent"] == "70.00"

    # JPY 独立口径
    assert body["by_currency"]["JPY"]["gmv"] == "1000"
    assert body["by_currency"]["JPY"]["avg_order_value"] == "1000"

    assert "profit" in body["formulas"]


def test_overview_filters_orders_outside_window(db_session_factory):
    orders = [
        {"number": "old", "amount": "999.00", "currency": "USD", "created": "2020-01-01T00:00:00+00:00"},
        {"number": "new", "amount": "10.00", "currency": "USD", "created": "2026-09-19T00:00:00+00:00"},
    ]
    client = _client(db_session_factory, orders)
    body = client.get("/api/v1/analytics/overview?days=30&currency=USD").json()
    assert body["by_currency"]["USD"]["order_count"] == "1"
    assert body["by_currency"]["USD"]["gmv"] == "10.00"


def test_formulas_endpoint(db_session_factory):
    client = _client(db_session_factory, [])
    resp = client.get("/api/v1/analytics/formulas")
    assert resp.status_code == 200
    assert "利润" in resp.json()["profit"]


def test_analytics_requires_admin():
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"

    async def customer():
        return CurrentUser(id="U2", email="buyer@example.com", is_staff=False)

    app.dependency_overrides[get_current_user] = customer
    assert TestClient(app).get("/api/v1/analytics/overview").status_code == 403


def test_invalid_other_cost_rejected(db_session_factory):
    client = _client(db_session_factory, [])
    assert client.get("/api/v1/analytics/overview?other_cost=abc").status_code == 422
