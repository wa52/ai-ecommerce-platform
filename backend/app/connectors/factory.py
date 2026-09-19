from functools import lru_cache

from app.connectors.base import CommerceAdapter
from app.connectors.saleor import SaleorAdapter
from app.infrastructure.config.settings import get_settings


@lru_cache
def get_commerce_adapter() -> CommerceAdapter:
    return SaleorAdapter(str(get_settings().saleor_api_url))
