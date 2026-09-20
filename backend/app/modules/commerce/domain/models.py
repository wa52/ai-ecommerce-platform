"""统一业务模型（spec §9）。

第三方平台/框架的原始 DTO 不得进入核心 Domain，必须先转换为统一模型。
当前由 Saleor 作为 Commerce Core，映射在 CommerceService 中完成。
"""

from pydantic import BaseModel, Field


class StoreChannel(BaseModel):
    """Store 的等价物：Saleor Channel（货币 / 国家 / 启用状态）。"""

    id: str
    name: str
    slug: str
    currency: str
    country: str | None = None
    is_active: bool = True


class UnifiedProductVariant(BaseModel):
    id: str
    sku: str | None = None
    quantity_available: int | None = None


class UnifiedProduct(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None = None
    product_type: str | None = None
    channels: list[str] = Field(default_factory=list)
    variant: UnifiedProductVariant | None = None


class UnifiedVariantStock(BaseModel):
    warehouse_id: str
    warehouse: str
    quantity: int


class UnifiedVariantDetail(BaseModel):
    id: str
    sku: str | None = None
    stocks: list[UnifiedVariantStock] = Field(default_factory=list)


class UnifiedProductDetail(UnifiedProduct):
    variants: list[UnifiedVariantDetail] = Field(default_factory=list)


class UnifiedOrderItem(BaseModel):
    id: str
    product_name: str
    sku: str | None = None
    quantity: int
    unit_amount: str
    currency: str


class UnifiedFulfillment(BaseModel):
    id: str
    status: str
    tracking_number: str = ""
    created_at: str = ""


class UnifiedOrder(BaseModel):
    id: str
    number: str
    status: str
    payment_status: str
    channel: str | None = None
    total_amount: str
    currency: str
    created_at: str
    items: list[UnifiedOrderItem] = Field(default_factory=list)
    fulfillments: list[UnifiedFulfillment] = Field(default_factory=list)


class UnifiedStock(BaseModel):
    variant_id: str
    sku: str | None = None
    warehouse: str
    quantity: int


class Page(BaseModel):
    total_count: int
    has_next_page: bool
    end_cursor: str | None = None
