from app.infrastructure.database.base import Base
from app.modules.ai.rag import models as _rag_models  # noqa: F401
from app.modules.ai.repository import models as _ai_models  # noqa: F401
from app.modules.finance.repository import models as _finance_models  # noqa: F401
from app.modules.store.repository import models as _store_models  # noqa: F401

__all__ = ["Base"]
