from functools import lru_cache

from app.connectors.factory import get_commerce_adapter
from app.modules.iam.application.service import IamService


@lru_cache
def get_iam_service() -> IamService:
    return IamService(get_commerce_adapter())
