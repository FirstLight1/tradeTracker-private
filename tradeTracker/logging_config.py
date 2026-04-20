import logging
import os
from logging.config import dictConfig


def configure_logging(app):
    is_prod = os.getenv("FLASK_ENV") == "prod"
    level = os.getenv("TRADETRACKER_LOG_LEVEL")
    if not level:
        level = "INFO" if is_prod else "DEBUG"
    if is_prod:
        base_dir = os.getenv("DATA_DIR", app.instance_path)
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
                    "maxBytes": 1024 * 1024 * 10,
                    "backupCount": 5,
                    "encoding": "utf-8",
                    "formatter": "detailed",
                },
                "slow_queries": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(log_dir, "slow_queries.log"),
                "maxBytes": 1024 * 1024 * 5,
                "backupCount": 3,
                "encoding": "utf-8",
                "formatter": "detailed",
                },
            },
            "loggers": {
                "tradetracker.db.slow": {
                    "level": "WARNING",
                    "handlers": ["slow_queries"],
                    "propagate": False,  # <-- this is the key part
                }
            },
            "root": {"level": level, "handlers": ["console", "file"]},
        }
    )
