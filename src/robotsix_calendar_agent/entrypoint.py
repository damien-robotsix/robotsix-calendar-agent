"""Long-lived in-process service entrypoint for :class:`CalendarAgent`.

Blocks until ``SIGTERM``/``SIGINT`` requests a graceful shutdown.
"""

from __future__ import annotations

import logging
import signal
import threading
from typing import Any

from .agent import CalendarAgent

logger = logging.getLogger(__name__)

__all__ = ["main"]


def _serve_blocking(agent: CalendarAgent) -> None:
    """Start *agent* and block until ``SIGTERM``/``SIGINT`` (in-process mode)."""
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    agent.start()
    logger.info("CalendarAgent service running; awaiting shutdown signal")
    try:
        stop_event.wait()
    finally:
        agent.stop()
        logger.info("CalendarAgent service stopped")


def main() -> None:
    """Run the calendar agent as a long-lived in-process service."""
    from .logging_config import configure_logging
    from .settings import Settings

    settings = Settings()
    configure_logging(level=settings.LOG_LEVEL, json_logs=settings.JSON_LOGS)
    _serve_blocking(CalendarAgent())
