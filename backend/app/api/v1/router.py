from fastapi import APIRouter

from app.api.v1 import health, tasks
from app.modules.ai.agent.api import router as agent_router
from app.modules.ai.api.routes import router as ai_router
from app.modules.ai.rag.api import router as rag_router
from app.modules.commerce.api.routes import router as commerce_router
from app.modules.finance.api.routes import router as finance_router
from app.modules.iam.api.routes import router as iam_router
from app.modules.store.api.routes import router as connectors_router
from app.modules.store.api.stores import router as stores_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tasks.router)
api_router.include_router(iam_router)
api_router.include_router(commerce_router)
api_router.include_router(connectors_router)
api_router.include_router(stores_router)
api_router.include_router(finance_router)
api_router.include_router(ai_router)
api_router.include_router(agent_router)
api_router.include_router(rag_router)
