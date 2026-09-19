import logging
import sys

from app.infrastructure.config.settings import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# 生产环境默认 INFO；可通过 LOG_LEVEL 覆盖
_NOISY = {
    "httpcore": logging.WARNING,
    "httpx": logging.WARNING,
    "uvicorn.access": logging.INFO,
    "sqlalchemy.engine": logging.WARNING,
    "python_multipart": logging.WARNING,
}


def setup_logging() -> None:
    settings = get_settings()
    level_name = (settings.log_level or "").upper()
    if level_name:
        level = getattr(logging, level_name, logging.INFO)
    else:
        level = logging.DEBUG if settings.app_env == "dev" else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    for name, noisy_level in _NOISY.items():
        logging.getLogger(name).setLevel(max(level, noisy_level))
