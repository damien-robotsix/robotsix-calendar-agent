"""Idempotent logging configuration for the calendar agent.

Provides a :func:`setup_logging` entry point that operators call once at
process start.  Uses only stdlib — no external dependencies.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Sequence
from typing import TextIO

#: Marker attribute set on handlers created by :func:`setup_logging` so a
#: repeat call can detect and reuse the existing handler (idempotency).
_CONFIGURED_MARKER = "_robotsix_calendar_agent_configured"

_CONSOLE_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _JsonFormatter(logging.Formatter):
    """Render each log record as a single line of JSON via stdlib ``json``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": self.formatTime(record),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(
    *,
    level: int | str = "INFO",
    fmt: str = "console",
    loggers: Sequence[str] = (),
    stream: TextIO | None = None,
) -> None:
    """Configure application logging (idempotent).

    Attaches a single :class:`logging.StreamHandler` to each named logger
    and sets each logger's level.  The root logger is never touched.

    Args:
        level: Level name (e.g. ``"DEBUG"``) or int.
        fmt: ``"console"`` or ``"json"``.  Unrecognised values fall back
            to ``"console"``.
        loggers: Logger names to configure.  Each gets a dedicated handler.
        stream: Target stream.  Defaults to :data:`sys.stdout`.
    """
    resolved_level: int = (
        level
        if isinstance(level, int)
        else logging.getLevelNamesMapping().get(str(level).upper(), logging.INFO)
    )
    formatter: logging.Formatter = (
        _JsonFormatter() if fmt == "json" else logging.Formatter(_CONSOLE_FORMAT)
    )
    target_stream = stream if stream is not None else sys.stdout

    for name in loggers:
        target = logging.getLogger(name)
        target.setLevel(resolved_level)
        target.propagate = False

        existing = next(
            (h for h in target.handlers if getattr(h, _CONFIGURED_MARKER, False)),
            None,
        )
        if existing is not None:
            existing.setFormatter(formatter)
            existing.setLevel(resolved_level)
            continue

        handler: logging.Handler = logging.StreamHandler(target_stream)
        handler.setFormatter(formatter)
        handler.setLevel(resolved_level)
        setattr(handler, _CONFIGURED_MARKER, True)
        target.addHandler(handler)
