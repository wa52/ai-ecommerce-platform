from pydantic import BaseModel, Field


class StoreCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: str = Field(pattern=r"^[a-z0-9_-]+$", max_length=50)
    currency: str = Field(default="USD", max_length=10)
    country: str | None = Field(default=None, max_length=10)
    credentials: dict[str, str] = Field(default_factory=dict)


class StoreUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, pattern=r"^(active|disabled)$")
    credentials: dict[str, str] | None = None


class StoreResponse(BaseModel):
    id: str
    name: str
    platform: str
    status: str
    currency: str
    country: str | None
    credentials_masked: str
    created_at: str
