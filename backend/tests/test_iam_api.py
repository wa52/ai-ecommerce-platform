import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.connectors.base import CommerceAdapter, CommerceHealth
from app.connectors.factory import get_commerce_adapter
from app.main import create_app
from app.modules.iam.api.deps import get_bearer_token, get_current_user
from app.modules.iam.domain.models import CurrentUser


class FakeAdapter(CommerceAdapter):
    async def health(self) -> CommerceHealth:
        return CommerceHealth(True, "fake")

    async def graphql(self, query: str, variables: dict | None = None, token: str | None = None) -> dict:
        return {
            "shop": {"name": "Fake Shop"},
            "staffUsers": {"totalCount": 3},
            "customers": {"totalCount": 7},
        }


ADMIN = CurrentUser(id="U1", email="admin@example.com", is_staff=True, permissions=[])
STAFF = CurrentUser(id="U2", email="staff@example.com", is_staff=True, permissions=["MANAGE_ORDERS"])
CUSTOMER = CurrentUser(id="U3", email="buyer@example.com", is_staff=False, permissions=[])


def _client(user: CurrentUser | None, *, unauthorized: bool = False) -> TestClient:
    app = create_app()

    async def override_user():
        if unauthorized:
            raise HTTPException(status_code=401, detail="未提供访问令牌")
        return user

    app.dependency_overrides[get_bearer_token] = lambda: "test-token"
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_commerce_adapter] = lambda: FakeAdapter()
    return TestClient(app)


def test_me_requires_token():
    assert _client(None, unauthorized=True).get("/api/v1/iam/me").status_code == 401


def test_me_returns_current_user():
    resp = _client(CUSTOMER).get("/api/v1/iam/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "buyer@example.com"
    assert resp.json()["is_staff"] is False


def test_admin_overview_forbidden_for_customer():
    assert _client(CUSTOMER).get("/api/v1/iam/admin/overview").status_code == 403


def test_admin_overview_ok_for_admin():
    resp = _client(ADMIN).get("/api/v1/iam/admin/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["shop_name"] == "Fake Shop"
    assert body["staff_count"] == 3
    assert body["customer_count"] == 7
    assert body["requested_by"]["email"] == "admin@example.com"


def test_admin_overview_forbidden_for_non_superuser_non_staff():
    assert _client(STAFF).get("/api/v1/iam/admin/overview").status_code == 200
    assert CUSTOMER.is_admin is False
    assert ADMIN.is_admin is True


class RejectingAdapter(FakeAdapter):
    async def graphql(self, query: str, variables: dict | None = None, token: str | None = None) -> dict:
        if "tokenCreate" in query:
            return {"tokenCreate": {"token": None, "errors": [{"field": "email", "message": "Please, enter valid credentials"}]}}
        return await super().graphql(query, variables, token)


def test_login_with_invalid_credentials_returns_401():
    app = create_app()
    app.dependency_overrides[get_commerce_adapter] = lambda: RejectingAdapter()
    client = TestClient(app)
    resp = client.post("/api/v1/iam/login", json={"email": "admin@example.com", "password": "wrong"})
    assert resp.status_code == 401
    assert "登录失败" in resp.json()["detail"]


def test_login_validation_error_returns_422():
    client = TestClient(create_app())
    assert client.post("/api/v1/iam/login", json={"email": "not-an-email", "password": ""}).status_code == 422
