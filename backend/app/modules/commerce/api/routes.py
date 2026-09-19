from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.connectors.base import CommerceAdapter
from app.connectors.factory import get_commerce_adapter
from app.modules.commerce.application.factory import get_commerce_service
from app.modules.commerce.application.service import CommerceError, CommerceService
from app.modules.commerce.domain.models import (
    Page,
    StoreChannel,
    UnifiedOrder,
    UnifiedProduct,
    UnifiedProductDetail,
    UnifiedStock,
    UnifiedVariantDetail,
)
from app.modules.iam.api.deps import AdminUserDep, get_bearer_token

router = APIRouter(prefix="/commerce", tags=["commerce"])

ServiceDep = Annotated[CommerceService, Depends(get_commerce_service)]


class ProductPage(BaseModel):
    items: list[UnifiedProduct]
    page: Page


class OrderPage(BaseModel):
    items: list[UnifiedOrder]
    page: Page


class StockPage(BaseModel):
    items: list[UnifiedStock]
    page: Page


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    description: str | None = None


class StockUpdateRequest(BaseModel):
    variant_id: str
    warehouse_id: str
    quantity: int = Field(ge=0)


class VariantCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=255)
    channel_id: str
    warehouse_id: str
    price: str = Field(pattern=r"^\d+(\.\d{1,2})?$")
    quantity: int = Field(default=0, ge=0)
    attributes: list[dict] = Field(default_factory=list)


def _handle(exc: CommerceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


# ---------- Store ----------


@router.get("/stores", response_model=list[StoreChannel])
async def list_stores(_: AdminUserDep, service: ServiceDep) -> list[StoreChannel]:
    return await service.list_stores()


# ---------- Product ----------


@router.get("/products", response_model=ProductPage)
async def list_products(
    _: AdminUserDep,
    service: ServiceDep,
    search: str | None = Query(default=None),
    slug: str | None = Query(default=None),
    first: int = Query(default=20, ge=1, le=100),
    after: str | None = Query(default=None),
) -> ProductPage:
    items, page = await service.list_products(search=search, first=first, after=after, slug=slug)
    return ProductPage(items=items, page=page)


@router.get("/products/{product_id}", response_model=UnifiedProductDetail)
async def get_product(product_id: str, _: AdminUserDep, service: ServiceDep) -> UnifiedProductDetail:
    try:
        return await service.get_product(product_id)
    except CommerceError as exc:
        raise _handle(exc) from exc


@router.post("/products/{product_id}/variants", response_model=UnifiedVariantDetail, status_code=201)
async def create_variant(
    product_id: str, req: VariantCreateRequest, _: AdminUserDep, service: ServiceDep
) -> UnifiedVariantDetail:
    try:
        return await service.create_variant(
            product_id=product_id,
            sku=req.sku,
            channel_id=req.channel_id,
            warehouse_id=req.warehouse_id,
            price=req.price,
            quantity=req.quantity,
            attributes=req.attributes,
        )
    except CommerceError as exc:
        raise _handle(exc) from exc


@router.post("/products/{product_id}/publish", status_code=204)
async def publish_product(product_id: str, channel_id: str, _: AdminUserDep, service: ServiceDep) -> None:
    try:
        await service.publish_to_channel(product_id=product_id, channel_id=channel_id)
    except CommerceError as exc:
        raise _handle(exc) from exc


@router.get("/products/{product_id}/variant-requirements")
async def variant_requirements(product_id: str, _: AdminUserDep, service: ServiceDep) -> dict:
    try:
        return await service.get_variant_attribute_requirements(product_id)
    except CommerceError as exc:
        raise _handle(exc) from exc


@router.post("/products", response_model=UnifiedProduct, status_code=201)
async def create_product(req: ProductCreateRequest, _: AdminUserDep, service: ServiceDep) -> UnifiedProduct:
    try:
        return await service.create_product(name=req.name, slug=req.slug, description=req.description)
    except CommerceError as exc:
        raise _handle(exc) from exc


@router.patch("/products/{product_id}", response_model=UnifiedProduct)
async def update_product(
    product_id: str, req: ProductUpdateRequest, _: AdminUserDep, service: ServiceDep
) -> UnifiedProduct:
    try:
        return await service.update_product(
            product_id=product_id, name=req.name, description=req.description
        )
    except CommerceError as exc:
        raise _handle(exc) from exc


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: str, _: AdminUserDep, service: ServiceDep) -> None:
    try:
        await service.delete_product(product_id)
    except CommerceError as exc:
        raise _handle(exc) from exc


# ---------- Order ----------


@router.get("/orders", response_model=OrderPage)
async def list_orders(
    _: AdminUserDep,
    service: ServiceDep,
    channel: str | None = Query(default=None, description="渠道 ID（非 slug）"),
    first: int = Query(default=20, ge=1, le=100),
    after: str | None = Query(default=None),
) -> OrderPage:
    items, page = await service.list_orders(channel=channel, first=first, after=after)
    return OrderPage(items=items, page=page)


@router.get("/orders/{order_id}", response_model=UnifiedOrder)
async def get_order(order_id: str, _: AdminUserDep, service: ServiceDep) -> UnifiedOrder:
    try:
        return await service.get_order(order_id)
    except CommerceError as exc:
        raise _handle(exc) from exc


# ---------- Inventory ----------


@router.get("/inventory", response_model=StockPage)
async def list_inventory(
    _: AdminUserDep,
    service: ServiceDep,
    first: int = Query(default=50, ge=1, le=100),
    after: str | None = Query(default=None),
) -> StockPage:
    items, page = await service.list_stock(first=first, after=after)
    return StockPage(items=items, page=page)


@router.get("/warehouses")
async def list_warehouses(_: AdminUserDep, adapter: CommerceAdapter = Depends(get_commerce_adapter), token: str = Depends(get_bearer_token)) -> list[dict]:
    data = await adapter.graphql("{ warehouses(first: 50) { edges { node { id name } } } }", token=token)
    return [e["node"] for e in ((data.get("warehouses") or {}).get("edges") or [])]


@router.post("/inventory", response_model=list[UnifiedStock])
async def update_inventory(
    req: StockUpdateRequest, _: AdminUserDep, service: ServiceDep
) -> list[UnifiedStock]:
    try:
        return await service.set_stock(
            variant_id=req.variant_id, warehouse_id=req.warehouse_id, quantity=req.quantity
        )
    except CommerceError as exc:
        raise _handle(exc) from exc
