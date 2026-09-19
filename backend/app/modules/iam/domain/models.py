from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentUser:
    """AI 扩展层的当前用户视图。

    Saleor 未暴露 isSuperuser，管理员语义由 is_staff 与 userPermissions 表达。
    """

    id: str
    email: str
    is_staff: bool
    permissions: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return self.is_staff


@dataclass(frozen=True)
class LoginResult:
    token: str
    refresh_token: str | None
    user: CurrentUser
