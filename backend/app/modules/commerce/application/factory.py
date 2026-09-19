from fastapi import Depends

from app.connectors.factory import get_commerce_adapter
from app.modules.commerce.application.service import CommerceService
from app.modules.iam.api.deps import get_bearer_token


def get_commerce_service(token: str = Depends(get_bearer_token)) -> CommerceService:
    """请求级服务：透传调用者令牌给 Commerce Core（最小权限）。"""
    return CommerceService(get_commerce_adapter(), token=token)
