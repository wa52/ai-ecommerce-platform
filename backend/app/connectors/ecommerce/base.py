"""平台 Connector 接口（spec §8）。

Commerce 核心不得直接依赖任何第三方平台 API，必须经 Connector 接口。
平台原始 DTO 不得泄漏到核心 Domain：Connector 负责转换为统一模型（spec §9）。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExternalProduct:
    external_id: str
    name: str
    sku: str | None = None
    price: str = "0"
    currency: str = "USD"
    quantity: int = 0
    description: str | None = None


@dataclass
class ExternalOrderItem:
    external_id: str
    product_name: str
    sku: str | None
    quantity: int
    unit_amount: str
    currency: str


@dataclass
class ExternalOrder:
    external_id: str
    number: str
    status: str
    payment_status: str
    currency: str
    total_amount: str
    created_at: str
    items: list[ExternalOrderItem] = field(default_factory=list)


@dataclass
class ExternalInventory:
    external_id: str
    sku: str | None
    quantity: int


@dataclass
class ConnectorHealth:
    ok: bool
    detail: str


class EcommerceConnector(ABC):
    """统一第三方电商平台接口。"""

    platform: str = "unknown"

    @abstractmethod
    async def health(self) -> ConnectorHealth: ...

    @abstractmethod
    async def get_products(self, *, limit: int = 50, cursor: str | None = None) -> tuple[list[ExternalProduct], str | None]: ...

    @abstractmethod
    async def get_orders(self, *, limit: int = 50, cursor: str | None = None) -> tuple[list[ExternalOrder], str | None]: ...

    @abstractmethod
    async def get_inventory(self, *, limit: int = 50, cursor: str | None = None) -> tuple[list[ExternalInventory], str | None]: ...
