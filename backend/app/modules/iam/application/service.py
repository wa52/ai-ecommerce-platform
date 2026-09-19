import logging

from app.connectors.base import CommerceAdapter
from app.modules.iam.domain.models import CurrentUser, LoginResult

logger = logging.getLogger(__name__)

_ME_QUERY = """
query Me {
  me {
    id
    email
    isStaff
    userPermissions { code }
  }
}
"""

_LOGIN_MUTATION = """
mutation Login($email: String!, $password: String!) {
  tokenCreate(email: $email, password: $password) {
    token
    refreshToken
    errors { field message code }
    user { id email isStaff }
  }
}
"""


class AuthError(Exception):
    """Raised when authentication or token validation fails."""


def _to_user(data: dict) -> CurrentUser:
    return CurrentUser(
        id=data.get("id", ""),
        email=data.get("email", ""),
        is_staff=bool(data.get("isStaff")),
        permissions=[p["code"] for p in (data.get("userPermissions") or [])],
    )


class IamService:
    """身份与权限：复用 Saleor 作为身份源，AI 扩展层只做校验与授权。

    AI 层不保存用户密码，也不复制 Saleor 的用户表（spec 2.1 框架职责边界）。
    """

    def __init__(self, adapter: CommerceAdapter):
        self._adapter = adapter

    async def login(self, email: str, password: str) -> LoginResult:
        data = await self._adapter.graphql(_LOGIN_MUTATION, {"email": email, "password": password})
        payload = data.get("tokenCreate") or {}
        if payload.get("errors"):
            detail = "; ".join(e.get("message", "") for e in payload["errors"])
            raise AuthError(f"登录失败：{detail}")
        if not payload.get("token"):
            raise AuthError("登录失败：未返回访问令牌")
        return LoginResult(
            token=payload["token"],
            refresh_token=payload.get("refreshToken"),
            user=_to_user(payload.get("user") or {"email": email}),
        )

    async def me(self, token: str) -> CurrentUser:
        try:
            data = await self._adapter.graphql(_ME_QUERY, token=token)
        except Exception as exc:
            logger.info("token validation failed: %s", type(exc).__name__)
            raise AuthError("访问令牌无效或已过期") from exc
        me = data.get("me")
        if not me:
            raise AuthError("访问令牌无效或已过期")
        return _to_user(me)
