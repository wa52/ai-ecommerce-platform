"""HTTP 中间件（spec §48 Trace/Request ID、§50 安全头）。"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app.http")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求生成/透传 Request ID，记录耗时，并附加安全响应头。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
            raise
        duration_ms = int((time.monotonic() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = str(duration_ms)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        logger.info(
            "%s %s -> %s (%dms) request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """统一异常出口：不泄漏内部细节（spec §50）。"""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):  # noqa: ANN001
        request_id = getattr(request.state, "request_id", "-")
        logger.exception("unhandled exception request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误，请稍后重试", "request_id": request_id},
        )


def install_middlewares(app: FastAPI, *, cors_origins: list[str]) -> None:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
