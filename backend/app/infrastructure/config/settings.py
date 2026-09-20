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
    log_level: str = ""
    api_v1_prefix: str = "/api/v1"

    database_url: PostgresDsn
    redis_url: RedisDsn
    saleor_api_url: str = "http://localhost:8000/graphql/"
    saleor_default_product_type_slug: str = "default-type"
    saleor_default_category_slug: str = "default-category"
    saleor_default_category_name: str = "Default Category"

    shopify_shop_domain: str = ""
    shopify_access_token: str = ""
    shopify_api_scheme: str = "https"

    store_credential_key: str = ""

    payment_webhook_secret: str = ""
    payment_provider: str = "alipay"
    alipay_gateway_url: str = "https://openapi.alipaydev.com/gateway.do"
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_notify_url: str = ""
    alipay_return_url: str = ""

    llm_provider: str = "openai_compatible"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_timeout: float = 30.0
    llm_max_retries: int = 2
    embedding_provider: str = "hashing"
    embedding_model: str = "text-embedding-3-small"

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
        ]
    )

    worker_queue: str = "tasks:default"
    worker_result_ttl: int = 3600
    worker_task_timeout: float = 60.0
    worker_task_max_retries: int = 1

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def _expand_scheme(cls, v: str, info: ValidationInfo) -> str:
        if isinstance(v, str) and v.startswith("postgres+asyncpg://"):
            return v.replace("postgres+asyncpg://", "postgresql+asyncpg://", 1)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
