from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI E-Commerce Platform"
    app_env: str = "dev"
    api_v1_prefix: str = "/api/v1"

    database_url: PostgresDsn
    redis_url: RedisDsn
    saleor_api_url: str = "http://localhost:8000/graphql/"
    saleor_default_product_type_slug: str = "default-type"
    saleor_default_category_slug: str = "default-category"
    saleor_default_category_name: str = "Default Category"

    shopify_shop_domain: str = ""
    shopify_access_token: str = ""

    store_credential_key: str = ""

    payment_webhook_secret: str = ""

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    worker_queue: str = "tasks:default"
    worker_result_ttl: int = 3600

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def _expand_scheme(cls, v: str, info: ValidationInfo) -> str:
        if isinstance(v, str) and v.startswith("postgres+asyncpg://"):
            return v.replace("postgres+asyncpg://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
