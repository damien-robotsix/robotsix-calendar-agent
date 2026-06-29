"""Idempotent logging configuration for the calendar agent.

Provides a :class:`JsonFormatter` for structured log output and a
:func:`configure_logging` entry point that operators call once at
process start.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Zero external dependencies — uses only stdlib :mod:`json`.
    """

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "time": self.formatTime(record),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(obj, default=str)


_configured: bool = False


def configure_logging(level: str, json_logs: bool) -> None:
    """One-shot logging setup — idempotent (safe to call more than once).

    Args:
        level: A valid Python log level name (e.g. ``"DEBUG"``).
        json_logs: If ``True``, attach a :class:`JsonFormatter` to
            the root logger's stderr handler; otherwise leave the
            default plain-text format.
    """
    global _configured
    if _configured:
        return
    _configured = True

    numeric = logging.getLevelName(level)
    root = logging.getLogger()

    if json_logs:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    else:
        logging.basicConfig(level=numeric)

    # basicConfig is a no-op when handlers already exist, so always
    # set the root logger level explicitly.
    root.setLevel(numeric)
