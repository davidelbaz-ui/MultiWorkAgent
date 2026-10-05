"""Structured logging for the Flask app."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app_config import AppConfig


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "structured", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(config: AppConfig) -> logging.Logger:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if config.log_json:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(getattr(logging, config.log_level, logging.INFO))
    from admin_log_buffer import install_log_buffer

    install_log_buffer(root)
    logger = logging.getLogger("bma")
    logger.setLevel(getattr(logging, config.log_level, logging.INFO))
    return logger


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        "(structured)",
        0,
        message,
        (),
        None,
    )
    record.structured = fields  # type: ignore[attr-defined]
    logger.handle(record)
