from fastapi import APIRouter

from app.api.v1 import health, tasks
from app.modules.commerce.api.routes import router as commerce_router
from app.modules.iam.api.routes import router as iam_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(tasks.router)
api_router.include_router(iam_router)
api_router.include_router(commerce_router)
