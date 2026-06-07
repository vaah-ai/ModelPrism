"""Structured logging configuration.

Provides JSON-formatted logging for production and plain-text for development.
"""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from typing import Any

from app.config import settings


class JSONFormatter(logging.Formatter):
    """JSON log formatter for production use.

    Outputs log records as JSON objects with timestamp, level, module,
    and message fields. Extra keyword arguments are included.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure root logger based on the runtime environment.

    In production (``environment != "development"``), JSON-formatted logs
    are output to stdout. In development, plain-text is used.
    """
    is_dev = settings.environment == "development"

    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "json" if not is_dev else "plain",
            "level": "DEBUG" if is_dev else "INFO",
        },
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JSONFormatter,
                },
                "plain": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": handlers,
            "root": {
                "level": "DEBUG" if is_dev else "INFO",
                "handlers": ["console"],
            },
            "loggers": {
                "sqlalchemy.engine": {
                    "level": "WARNING",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        }
    )
