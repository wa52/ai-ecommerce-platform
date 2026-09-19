from cryptography.fernet import Fernet, InvalidToken

from app.infrastructure.config.settings import get_settings


class CredentialCipherError(Exception):
    pass


def _cipher() -> Fernet:
    key = get_settings().store_credential_key
    if not key:
        raise CredentialCipherError(
            "缺少 STORE_CREDENTIAL_KEY 环境变量，无法加密店铺凭据。"
            "请生成一个 Fernet 密钥：python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise CredentialCipherError(
            "STORE_CREDENTIAL_KEY 不是合法的 Fernet 密钥（需 32 字节 urlsafe base64）。"
        ) from exc


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise CredentialCipherError("凭据解密失败：密钥不匹配或数据已损坏") from exc


def mask(secret: str) -> str:
    """用于展示的脱敏形式，绝不返回明文。"""
    if not secret:
        return ""
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}{'*' * 8}{secret[-2:]}"
