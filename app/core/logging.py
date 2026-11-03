"""Logging setup. Phone numbers must never be logged; log `user_ref` (a short hash prefix) instead."""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Query-string parameters whose values must never appear in logs. Meta's webhook
# verification puts the verify token in the URL, and uvicorn logs every URL.
_SECRET_PARAMS = re.compile(
    r"((?:hub[._]verify_token|access_token|token|key|secret)=)[^&\s\"']+", re.IGNORECASE
)


def redact(text: str) -> str:
    return _SECRET_PARAMS.sub(r"\1***", text)


class RedactSecretsFilter(logging.Filter):
    """Masks secret query parameters in log records (including uvicorn's access log)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            args = record.args if isinstance(record.args, tuple) else (record.args,)
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in args)
        return True


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_ContextFilter())
    handler.addFilter(RedactSecretsFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Third-party libraries are noisy at INFO.
    for noisy in ("httpx", "httpcore", "openai", "sqlalchemy.engine", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    # uvicorn's loggers use their own handlers (propagate=False), so filter them at the logger.
    for name in ("uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretsFilter) for f in uv_logger.filters):
            uv_logger.addFilter(RedactSecretsFilter())
