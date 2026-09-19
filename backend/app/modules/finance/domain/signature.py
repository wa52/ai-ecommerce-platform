import hashlib
import hmac

from app.modules.finance.domain.money import exponent_of, money


class WebhookSignatureError(Exception):
    pass


def verify_webhook_signature(*, payload: bytes, signature: str, secret: str, algorithm: str = "sha256") -> None:
    """Webhook 验签（spec §41）。签名不合法时抛错，调用方必须拒绝处理。"""
    if not secret:
        raise WebhookSignatureError("缺少 Webhook 签名密钥")
    if not signature:
        raise WebhookSignatureError("缺少签名")
    expected = hmac.new(secret.encode(), payload, getattr(hashlib, algorithm)).hexdigest()
    provided = signature.split("=", 1)[-1].strip()
    if not hmac.compare_digest(expected, provided):
        raise WebhookSignatureError("Webhook 签名校验失败")


def sign_payload(*, payload: bytes, secret: str, algorithm: str = "sha256") -> str:
    """供测试与本地联调生成签名。"""
    digest = hmac.new(secret.encode(), payload, getattr(hashlib, algorithm)).hexdigest()
    return f"{algorithm}={digest}"


__all__ = ["WebhookSignatureError", "verify_webhook_signature", "sign_payload", "money", "exponent_of"]
