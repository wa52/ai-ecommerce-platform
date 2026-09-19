from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.modules.iam.application.factory import get_iam_service
from app.modules.iam.application.service import AuthError, IamService
from app.modules.iam.domain.models import CurrentUser

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供访问令牌",
            headers=_UNAUTHORIZED_HEADERS,
        )
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    token: str = Depends(get_bearer_token),
    service: IamService = Depends(get_iam_service),
) -> CurrentUser:
    try:
        return await service.me(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=_UNAUTHORIZED_HEADERS,
        ) from exc


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
BearerTokenDep = Annotated[str, Depends(get_bearer_token)]
