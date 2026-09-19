from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.infrastructure.config.checks import run_startup_checks
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.session import engine
from app.infrastructure.logging.setup import setup_logging
from app.infrastructure.redis.client import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await run_startup_checks(engine, fail_fast=True)
    yield
    await engine.dispose()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
