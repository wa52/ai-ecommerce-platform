from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.security.crypto import decrypt, encrypt
from app.modules.store.repository.models import PlatformStore


class StoreNotFound(Exception):
    pass


class StoreRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        *,
        name: str,
        platform: str,
        currency: str,
        country: str | None,
        credentials: dict[str, str],
    ) -> PlatformStore:
        import json

        store = PlatformStore(
            name=name,
            platform=platform.lower(),
            status="active",
            currency=currency,
            country=country,
            credentials_encrypted=encrypt(json.dumps(credentials, ensure_ascii=False)),
        )
        self._session.add(store)
        await self._session.commit()
        await self._session.refresh(store)
        return store

    async def get(self, store_id: str) -> PlatformStore:
        store = await self._session.get(PlatformStore, store_id)
        if store is None:
            raise StoreNotFound(f"店铺不存在：{store_id}")
        return store

    async def list(self, *, platform: str | None = None) -> list[PlatformStore]:
        stmt = select(PlatformStore).order_by(PlatformStore.created_at.desc())
        if platform:
            stmt = stmt.where(PlatformStore.platform == platform.lower())
        return list((await self._session.execute(stmt)).scalars())

    async def update(
        self,
        store_id: str,
        *,
        name: str | None = None,
        status: str | None = None,
        credentials: dict[str, str] | None = None,
    ) -> PlatformStore:
        import json

        store = await self.get(store_id)
        if name is not None:
            store.name = name
        if status is not None:
            store.status = status
        if credentials is not None:
            store.credentials_encrypted = encrypt(json.dumps(credentials, ensure_ascii=False))
        await self._session.commit()
        await self._session.refresh(store)
        return store

    @staticmethod
    def credentials_of(store: PlatformStore) -> dict[str, str]:
        import json

        return json.loads(decrypt(store.credentials_encrypted))

    @staticmethod
    def created_at(store: PlatformStore) -> datetime:
        return store.created_at
