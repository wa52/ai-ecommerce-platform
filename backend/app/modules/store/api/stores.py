from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.security.crypto import mask
from app.modules.iam.api.deps import AdminUserDep
from app.modules.store.domain.models import StoreCreateRequest, StoreResponse, StoreUpdateRequest
from app.modules.store.repository.models import PlatformStore
from app.modules.store.repository.store_repository import StoreNotFound, StoreRepository

router = APIRouter(prefix="/stores", tags=["stores"])


def _to_response(store: PlatformStore) -> StoreResponse:
    credentials = StoreRepository.credentials_of(store)
    primary = next(iter(credentials.values()), "")
    return StoreResponse(
        id=store.id,
        name=store.name,
        platform=store.platform,
        status=store.status,
        currency=store.currency,
        country=store.country,
        credentials_masked=mask(primary),
        created_at=store.created_at.isoformat(),
    )


@router.post("", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def create_store(
    req: StoreCreateRequest, _: AdminUserDep, db: AsyncSession = Depends(get_db)
) -> StoreResponse:
    repo = StoreRepository(db)
    store = await repo.create(
        name=req.name,
        platform=req.platform,
        currency=req.currency,
        country=req.country,
        credentials=req.credentials,
    )
    return _to_response(store)


@router.get("", response_model=list[StoreResponse])
async def list_stores(
    _: AdminUserDep, db: AsyncSession = Depends(get_db), platform: str | None = None
) -> list[StoreResponse]:
    stores = await StoreRepository(db).list(platform=platform)
    return [_to_response(s) for s in stores]


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(store_id: str, _: AdminUserDep, db: AsyncSession = Depends(get_db)) -> StoreResponse:
    try:
        return _to_response(await StoreRepository(db).get(store_id))
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: str, req: StoreUpdateRequest, _: AdminUserDep, db: AsyncSession = Depends(get_db)
) -> StoreResponse:
    try:
        store = await StoreRepository(db).update(
            store_id, name=req.name, status=req.status, credentials=req.credentials
        )
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(store)


@router.post("/{store_id}/disable", response_model=StoreResponse)
async def disable_store(store_id: str, _: AdminUserDep, db: AsyncSession = Depends(get_db)) -> StoreResponse:
    try:
        store = await StoreRepository(db).update(store_id, status="disabled")
    except StoreNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(store)
