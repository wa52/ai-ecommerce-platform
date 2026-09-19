import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.infrastructure.database.base import Base
from app.infrastructure.security.crypto import CredentialCipherError, decrypt, encrypt, mask
from app.main import create_app
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser

ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True)


def test_encrypt_roundtrip_and_mask():
    token = encrypt("shpat_secret_value_1234")
    assert token != "shpat_secret_value_1234"
    assert decrypt(token) == "shpat_secret_value_1234"
    masked = mask("shpat_secret_value_1234")
    assert "secret" not in masked
    assert masked.startswith("shpa")
    assert masked.endswith("34")


def test_encrypt_requires_key(monkeypatch):
    from app.infrastructure.config.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "store_credential_key", "")
    with pytest.raises(CredentialCipherError):
        encrypt("x")


def test_platform_store_model_registered():
    assert "platform_stores" in Base.metadata.tables
    columns = set(Base.metadata.tables["platform_stores"].columns.keys())
    assert {"id", "name", "platform", "status", "currency", "country", "credentials_encrypted"} <= columns


def test_store_endpoints_require_admin():
    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"

    async def customer():
        return CurrentUser(id="U2", email="buyer@example.com", is_staff=False)

    app.dependency_overrides[get_current_user] = customer
    client = TestClient(app)
    assert client.get("/api/v1/stores").status_code == 403


def test_store_crud_and_credential_never_returned(db_session_factory):
    """凭据必须加密落库，且 API 永不返回明文。"""
    from app.modules.store.repository.store_repository import StoreRepository

    app = create_app()
    app.dependency_overrides[get_bearer_token] = lambda: "t"
    app.dependency_overrides[get_current_user] = lambda: ADMIN

    async def override_db():
        async with db_session_factory() as session:
            yield session

    from app.infrastructure.database.session import get_db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    created = client.post(
        "/api/v1/stores",
        json={
            "name": "Shopify Store A",
            "platform": "shopify",
            "currency": "USD",
            "country": "US",
            "credentials": {"access_token": "shpat_super_secret_token"},
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert "credentials" not in body
    assert "shpat_super_secret_token" not in created.text
    assert body["credentials_masked"] and "secret" not in body["credentials_masked"]

    listed = client.get("/api/v1/stores")
    assert listed.status_code == 200
    assert listed.json()[0]["platform"] == "shopify"
    assert "shpat_super_secret_token" not in listed.text

    disabled = client.post(f"/api/v1/stores/{body['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    missing = client.get("/api/v1/stores/does-not-exist")
    assert missing.status_code == 404
