from decimal import Decimal

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.modules.finance.alipay import AlipayClient


def _client() -> AlipayClient:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return AlipayClient(
        gateway_url="https://openapi.alipaydev.com/gateway.do",
        app_id="2026000000000000",
        private_key=private_pem,
        public_key=public_pem,
        notify_url="https://shop.example.com/api/v1/finance/alipay/notify",
        return_url="https://shop.example.com/payment/alipay/return",
    )


def test_page_pay_form_is_signed_and_contains_cny_amount():
    client = _client()
    html = client.build_page_pay_form(
        out_trade_no="order-100",
        subject="扬声器",
        total_amount=Decimal("12.34"),
    )
    assert "alipay.trade.page.pay" in html
    assert "12.34" in html
    assert "name=\"sign\"" in html


def test_notification_signature_round_trip():
    client = _client()
    client.build_page_pay_form(out_trade_no="order-101", subject="商品", total_amount=Decimal("1.00"))
    # Build a notification using the client's private signing path through a payment form signature.
    params = {
        "app_id": client.app_id,
        "trade_status": "TRADE_SUCCESS",
        "out_trade_no": "order-101",
        "trade_no": "2026000000000000001",
        "total_amount": "1.00",
        "sign_type": "RSA2",
    }
    signature = client._sign({k: v for k, v in params.items() if k != "sign_type"})
    params["sign"] = signature
    assert client.verify_notification(params)
    params["total_amount"] = "2.00"
    assert not client.verify_notification(params)
