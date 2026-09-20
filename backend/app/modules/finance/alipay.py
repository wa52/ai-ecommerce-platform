"""支付宝电脑网站支付（RSA2）协议客户端。"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from decimal import Decimal
from html import escape

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class AlipayError(Exception):
    pass


class AlipayNotConfigured(AlipayError):
    pass


def _clean_key(value: str) -> bytes:
    return value.replace("\\n", "\n").encode()


def _sorted_sign_content(params: dict[str, str]) -> str:
    return "&".join(f"{key}={value}" for key, value in sorted(params.items()) if value != "")


def _load_private_key(value: str) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(_clean_key(value), password=None)
    except (ValueError, TypeError) as exc:
        raise AlipayError("支付宝商户私钥不是有效的 PEM 格式") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise AlipayError("支付宝商户私钥必须是 RSA 私钥")
    return key


def _load_public_key(value: str) -> rsa.RSAPublicKey:
    try:
        key = serialization.load_pem_public_key(_clean_key(value))
    except (ValueError, TypeError) as exc:
        raise AlipayError("支付宝公钥不是有效的 PEM 格式") from exc
    if not isinstance(key, rsa.RSAPublicKey):
        raise AlipayError("支付宝公钥必须是 RSA 公钥")
    return key


class AlipayClient:
    def __init__(self, *, gateway_url: str, app_id: str, private_key: str, public_key: str,
                 notify_url: str, return_url: str, timeout: float = 15.0) -> None:
        self.gateway_url = gateway_url
        self.app_id = app_id
        self.private_key = private_key
        self.public_key = public_key
        self.notify_url = notify_url
        self.return_url = return_url
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return all((self.app_id, self.private_key, self.public_key, self.notify_url, self.return_url))

    def _require_configured(self) -> None:
        if not self.enabled:
            raise AlipayNotConfigured(
                "支付宝未配置完整：需要 ALIPAY_APP_ID、ALIPAY_PRIVATE_KEY、ALIPAY_PUBLIC_KEY、"
                "ALIPAY_NOTIFY_URL、ALIPAY_RETURN_URL"
            )

    def _sign(self, params: dict[str, str]) -> str:
        signature = _load_private_key(self.private_key).sign(
            _sorted_sign_content(params).encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
        )
        return base64.b64encode(signature).decode("ascii")

    def verify_notification(self, params: dict[str, str]) -> bool:
        self._require_configured()
        signature = params.get("sign", "")
        if not signature or params.get("sign_type", "RSA2") != "RSA2":
            return False
        verify_params = {k: str(v) for k, v in params.items() if k not in {"sign", "sign_type"}}
        try:
            _load_public_key(self.public_key).verify(
                base64.b64decode(signature), _sorted_sign_content(verify_params).encode("utf-8"),
                padding.PKCS1v15(), hashes.SHA256()
            )
        except (InvalidSignature, ValueError, TypeError):
            return False
        return params.get("app_id") == self.app_id

    def build_page_pay_form(self, *, out_trade_no: str, subject: str, total_amount: Decimal,
                            body: str = "") -> str:
        self._require_configured()
        if total_amount <= 0:
            raise AlipayError("支付宝支付金额必须大于 0")
        params = {
            "app_id": self.app_id, "method": "alipay.trade.page.pay", "format": "JSON",
            "charset": "utf-8", "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "version": "1.0",
            "notify_url": self.notify_url, "return_url": self.return_url,
            "biz_content": json.dumps({"product_code": "FAST_INSTANT_TRADE_PAY",
                "out_trade_no": out_trade_no, "subject": subject,
                "total_amount": f"{total_amount:.2f}", "body": body},
                ensure_ascii=False, separators=(",", ":")),
        }
        params["sign"] = self._sign(params)
        fields = "".join(f'<input type="hidden" name="{escape(k)}" value="{escape(v)}">'
                          for k, v in params.items())
        return f'<form id="alipay" method="post" action="{escape(self.gateway_url)}">{fields}' \
               "</form><script>document.getElementById('alipay').submit();</script>"

    async def refund(self, *, out_trade_no: str, refund_amount: Decimal,
                     out_request_no: str, refund_reason: str = "用户退款") -> dict:
        self._require_configured()
        params = {
            "app_id": self.app_id, "method": "alipay.trade.refund", "format": "JSON",
            "charset": "utf-8", "sign_type": "RSA2",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "version": "1.0",
            "biz_content": json.dumps({"out_trade_no": out_trade_no,
                "refund_amount": f"{refund_amount:.2f}", "refund_reason": refund_reason,
                "out_request_no": out_request_no}, ensure_ascii=False, separators=(",", ":")),
        }
        params["sign"] = self._sign(params)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.gateway_url, data=params)
            response.raise_for_status()
            payload = response.json()
        result = payload.get("alipay_trade_refund_response", {})
        if result.get("code") != "10000":
            raise AlipayError(result.get("sub_msg") or result.get("msg") or "支付宝退款失败")
        return result


def client_from_settings(settings) -> AlipayClient:
    return AlipayClient(gateway_url=settings.alipay_gateway_url, app_id=settings.alipay_app_id,
                        private_key=settings.alipay_private_key, public_key=settings.alipay_public_key,
                        notify_url=settings.alipay_notify_url, return_url=settings.alipay_return_url)
