import logging
import sys

from app.infrastructure.config.settings import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging() -> None:
    settings = get_settings()
    level = logging.DEBUG if settings.app_env == "dev" else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING if noisy == "sqlalchemy.engine" else logging.INFO)
