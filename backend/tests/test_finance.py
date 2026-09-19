from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.infrastructure.database.session import get_db
from app.main import create_app
from app.modules.finance.domain.money import MoneyError, money, mul, sub
from app.modules.finance.domain.signature import WebhookSignatureError, sign_payload, verify_webhook_signature
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)
SECRET = "test-webhook-secret"


def _client(db_session_factory):
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN

    async def override_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


# ---------- money ----------


def test_money_rejects_float():
    with pytest.raises(MoneyError):
        money(1.5, "USD")


def test_money_quantizes_by_currency():
    assert money("10.005", "USD") == Decimal("10.01")
    assert money("10.5", "JPY") == Decimal("11")  # JPY 无小数位，half-up 进位
    assert money("0.1", "USD") + money("0.2", "USD") == Decimal("0.30")


def test_money_requires_currency():
    with pytest.raises(MoneyError):
        money("1", "")


def test_mul_and_sub_are_decimal_safe():
    assert mul(Decimal("19.99"), Decimal("3"), "USD") == Decimal("59.97")
    assert sub(Decimal("100.00"), Decimal("0.01"), "USD") == Decimal("99.99")


# ---------- signature ----------


def test_webhook_signature_valid_and_invalid():
    payload = b'{"id":"evt_1"}'
    signature = sign_payload(payload=payload, secret=SECRET)
    verify_webhook_signature(payload=payload, signature=signature, secret=SECRET)
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(payload=payload, signature="sha256=deadbeef", secret=SECRET)
    with pytest.raises(WebhookSignatureError):
        verify_webhook_signature(payload=payload, signature=signature, secret="wrong-secret")


# ---------- payment idempotency ----------


def test_payment_is_idempotent(db_session_factory):
    client = _client(db_session_factory)
    body = {
        "order_ref": "order-1",
        "provider": "stripe",
        "amount": "100.00",
        "currency": "USD",
        "idempotency_key": "pay-key-1",
    }
    first = client.post("/api/v1/finance/payments", json=body)
    assert first.status_code == 201
    assert first.json()["created"] is True

    for _ in range(3):
        repeat = client.post("/api/v1/finance/payments", json=body)
        assert repeat.status_code == 201
        assert repeat.json()["id"] == first.json()["id"]
        assert repeat.json()["created"] is False

    payments = client.get("/api/v1/finance/payments").json()
    assert len([p for p in payments if p["idempotency_key"] == "pay-key-1"]) == 1

    ledger = client.get("/api/v1/finance/ledger").json()
    assert len([e for e in ledger if e["entry_type"] == "payment" and e["reference"] == first.json()["id"]]) == 1


def test_payment_rejects_zero_and_invalid(db_session_factory):
    client = _client(db_session_factory)
    zero = client.post(
        "/api/v1/finance/payments",
        json={"order_ref": "o", "provider": "stripe", "amount": "0.00", "currency": "USD", "idempotency_key": "k0"},
    )
    assert zero.status_code == 422
    invalid = client.post(
        "/api/v1/finance/payments",
        json={"order_ref": "o", "provider": "stripe", "amount": "abc", "currency": "USD", "idempotency_key": "k1"},
    )
    assert invalid.status_code == 422


# ---------- refunds ----------


def test_partial_and_full_refund_with_limit(db_session_factory):
    client = _client(db_session_factory)
    payment = client.post(
        "/api/v1/finance/payments",
        json={
            "order_ref": "order-2",
            "provider": "stripe",
            "amount": "100.00",
            "currency": "USD",
            "idempotency_key": "pay-key-2",
        },
    ).json()

    partial = client.post(
        "/api/v1/finance/refunds",
        json={"payment_id": payment["id"], "amount": "30.00", "idempotency_key": "rfd-1", "reason": "damaged"},
    )
    assert partial.status_code == 201
    assert partial.json()["amount"] == "30.00"

    # 重复退款请求（同 key）不产生新交易
    repeat = client.post(
        "/api/v1/finance/refunds",
        json={"payment_id": payment["id"], "amount": "30.00", "idempotency_key": "rfd-1"},
    )
    assert repeat.json()["created"] is False
    assert len(client.get("/api/v1/finance/refunds").json()) == 1

    # 超额退款被拒绝
    over = client.post(
        "/api/v1/finance/refunds",
        json={"payment_id": payment["id"], "amount": "80.00", "idempotency_key": "rfd-2"},
    )
    assert over.status_code == 409

    # 剩余可退额度内可继续退
    rest = client.post(
        "/api/v1/finance/refunds",
        json={"payment_id": payment["id"], "amount": "70.00", "idempotency_key": "rfd-3"},
    )
    assert rest.status_code == 201
    updated = client.get(f"/api/v1/finance/payments/{payment['id']}").json()
    assert updated["refunded_amount"] == "100.00"

    # 全额退完后不可再退
    blocked = client.post(
        "/api/v1/finance/refunds",
        json={"payment_id": payment["id"], "amount": "0.01", "idempotency_key": "rfd-4"},
    )
    assert blocked.status_code == 409


# ---------- settlement & reconciliation ----------


def test_settlement_fee_computation_and_reconciliation(db_session_factory):
    client = _client(db_session_factory)
    settlement = client.post(
        "/api/v1/finance/settlements",
        json={
            "platform": "shopify",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "currency": "USD",
            "platform_fee_rate": "5",
            "payment_fee_rate": "2",
            "items": [
                {"order_ref": "order-1", "gross_amount": "1000.00"},
                {"order_ref": "order-2", "gross_amount": "500.00"},
            ],
        },
    )
    assert settlement.status_code == 201
    body = settlement.json()
    # 手续费：1500 * 5% = 75；1500 * 2% = 30；净额 = 1500 - 75 - 30 = 1395
    assert body["gross_amount"] == "1500.00"
    assert body["platform_fee"] == "75.00"
    assert body["payment_fee"] == "30.00"
    assert body["net_amount"] == "1395.00"

    matched = client.post(
        "/api/v1/finance/reconciliations",
        json={"settlement_id": body["id"], "actual_net": "1395.00"},
    )
    assert matched.status_code == 201
    assert matched.json()["status"] == "matched"
    assert matched.json()["difference"] == "0.00"

    mismatched = client.post(
        "/api/v1/finance/reconciliations",
        json={"settlement_id": body["id"], "actual_net": "1390.00", "note": "平台扣款差异"},
    )
    assert mismatched.json()["status"] == "mismatched"
    assert mismatched.json()["difference"] == "-5.00"


# ---------- webhook ----------


def test_webhook_requires_valid_signature(db_session_factory):
    client = _client(db_session_factory)
    payload = b'{"id":"evt_100","order_ref":"order-9","amount":"10.00","currency":"USD"}'

    bad = client.post("/api/v1/finance/webhooks/stripe", content=payload, headers={"X-Signature": "sha256=bad"})
    assert bad.status_code == 401

    good_sig = sign_payload(payload=payload, secret=SECRET)
    first = client.post("/api/v1/finance/webhooks/stripe", content=payload, headers={"X-Signature": good_sig})
    assert first.status_code == 200
    assert first.json()["duplicate"] is False

    # 重复投递同一事件 -> 只产生一次交易
    second = client.post("/api/v1/finance/webhooks/stripe", content=payload, headers={"X-Signature": good_sig})
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["payment_id"] == first.json()["payment_id"]

    payments = client.get("/api/v1/finance/payments").json()
    assert len([p for p in payments if p["order_ref"] == "order-9"]) == 1


def test_webhook_rejects_malformed_payload(db_session_factory):
    client = _client(db_session_factory)
    payload = b"not-json"
    signature = sign_payload(payload=payload, secret=SECRET)
    resp = client.post("/api/v1/finance/webhooks/stripe", content=payload, headers={"X-Signature": signature})
    assert resp.status_code == 422


# ---------- authorization ----------


def test_finance_requires_admin():
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"

    async def customer():
        return CurrentUser(id="U2", email="buyer@example.com", is_staff=False)

    app.dependency_overrides[get_current_user] = customer
    client = TestClient(app)
    assert client.get("/api/v1/finance/payments").status_code == 403
