import logging
import os
import sys
from logging.config import dictConfig


def configure_logging(app):
    is_frozen = getattr(sys, "frozen", False)
    level = os.getenv("TRADETRACKER_LOG_LEVEL")
    if not level:
        level = "INFO" if is_frozen else "DEBUG"
    if is_frozen:
        base_dir = os.path.join(os.environ["APPDATA"], "TradeTracker")
    else:
        base_dir = app.instance_path
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "tradetracker.log")
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
                },
                "detailed": {
                    "format": "[%(asctime)s] %(levelname)s %(name)s %(module)s:%(lineno)d - %(message)s"
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://flask.logging.wsgi_errors_stream",
                    "formatter": "default",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": log_file,
                    "maxBytes": 5_000_000,
                    "backupCount": 5,
                    "encoding": "utf-8",
                    "formatter": "detailed",
                },
            },
            "root": {"level": level, "handlers": ["console", "file"]},
        }
    )
