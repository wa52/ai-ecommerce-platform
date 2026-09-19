from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.connectors.base import CommerceAdapter
from app.connectors.factory import get_commerce_adapter
from app.modules.iam.api.deps import AdminUserDep, BearerTokenDep, CurrentUserDep
from app.modules.iam.application.factory import get_iam_service
from app.modules.iam.application.service import AuthError, IamService

router = APIRouter(prefix="/iam", tags=["iam"])

_ADMIN_OVERVIEW_QUERY = """
query AdminOverview {
  shop { name }
  staffUsers(first: 1) { totalCount }
  customers(first: 1) { totalCount }
}
"""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    email: str
    is_staff: bool
    permissions: list[str]


class LoginResponse(BaseModel):
    token: str
    refresh_token: str | None
    user: UserResponse


class AdminOverviewResponse(BaseModel):
    shop_name: str
    staff_count: int
    customer_count: int
    requested_by: UserResponse


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest, request: Request, service: IamService = Depends(get_iam_service)
) -> LoginResponse:
    from app.infrastructure.http.ratelimit import RateLimiter

    limiter = RateLimiter(limit=10, window_seconds=60, prefix="login")
    client_key = request.client.host if request.client else "unknown"
    allowed, remaining = await limiter.check(client_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录尝试过于频繁，请稍后重试",
            headers={"Retry-After": "60"},
        )
    try:
        result = await service.login(req.email, req.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LoginResponse(
        token=result.token,
        refresh_token=result.refresh_token,
        user=UserResponse(**result.user.__dict__),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUserDep) -> UserResponse:
    return UserResponse(**user.__dict__)


@router.get("/admin/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    user: AdminUserDep,
    token: BearerTokenDep,
    adapter: CommerceAdapter = Depends(get_commerce_adapter),
) -> AdminOverviewResponse:
    try:
        data = await adapter.graphql(_ADMIN_OVERVIEW_QUERY, token=token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="上游 Commerce Core 查询失败",
        ) from exc
    return AdminOverviewResponse(
        shop_name=data.get("shop", {}).get("name", ""),
        staff_count=data.get("staffUsers", {}).get("totalCount", 0),
        customer_count=data.get("customers", {}).get("totalCount", 0),
        requested_by=UserResponse(**user.__dict__),
    )
