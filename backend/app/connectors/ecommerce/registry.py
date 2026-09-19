"""Connector 注册表：按平台名解析 Connector 实例（spec §8 插件化）。"""

from functools import lru_cache

from app.connectors.ecommerce.base import EcommerceConnector
from app.connectors.ecommerce.shopify import ShopifyConnector
from app.infrastructure.config.settings import get_settings


class ConnectorNotConfigured(Exception):
    pass


@lru_cache
def get_shopify_connector() -> ShopifyConnector:
    settings = get_settings()
    return ShopifyConnector(settings.shopify_shop_domain, settings.shopify_access_token, scheme=settings.shopify_api_scheme)


def get_connector(platform: str) -> EcommerceConnector:
    platform = (platform or "").lower()
    if platform == "shopify":
        return get_shopify_connector()
    raise ConnectorNotConfigured(f"暂不支持的平台：{platform}")


def list_platforms() -> list[dict]:
    settings = get_settings()
    shopify = get_shopify_connector()
    return [
        {
            "platform": "shopify",
            "configured": shopify.configured,
            "shop_domain": settings.shopify_shop_domain or None,
        }
    ]
