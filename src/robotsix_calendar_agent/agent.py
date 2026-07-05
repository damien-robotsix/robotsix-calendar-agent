"""CalendarAgent — calendar/contacts management agent.

Wires together :class:`IntentParser`, :class:`CalDavClient` into a
single runnable agent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
import time
from typing import Any

try:
    from robotsix_llmio.core import setup_langfuse_tracing  # pragma: no cover

    setup_langfuse_tracing()
except ImportError:  # pragma: no cover
    pass

from .caldav_client import (
    CalDavClient,
    CalendarEvent,
    Contact,
    OperationError,
    Task,
)
from .dispatch import _CREATE_UPDATE_HANDLERS, _DISPATCH
from .intent_parser import (
    CalendarOperation,
    ContactOperation,
    IntentParseError,
    IntentParser,
    ParsedIntent,
    TaskOperation,
)

logger = logging.getLogger(__name__)

__all__ = [
    "CalDavClient",
    "CalendarAgent",
    "CalendarEvent",
    "CalendarOperation",
    "Contact",
    "ContactOperation",
    "IntentParseError",
    "IntentParser",
    "OperationError",
    "ParsedIntent",
    "Task",
    "TaskOperation",
]


class CalendarAgent:
    """Top-level agent that provides calendar/contact operations.

    Creates a :class:`CalDavClient` and :class:`IntentParser`.  The
    dispatch table (:func:`_dispatch`) maps parsed intents to CalDAV
    operations; callers can use it directly.

    Args:
        agent_id: Agent ID (default ``"calendar"``).
        radicale_url: Radicale server URL (falls back to env
            ``RADICALE_URL``).
        radicale_username: Radicale username (falls back to env
            ``RADICALE_USERNAME``).
        radicale_password: Radicale password (falls back to env
            ``RADICALE_PASSWORD``).
        llm_model_config: Forwarded to :class:`IntentParser` for llmio
            model selection.

    Raises:
        ValueError: If Radicale credentials are missing after
            constructor-arg + env-var fallback.
    """

    def __init__(
        self,
        agent_id: str = "calendar",
        *,
        radicale_url: str | None = None,
        radicale_username: str | None = None,
        radicale_password: str | None = None,
        llm_model_config: dict[str, Any] | None = None,
    ) -> None:
        from .settings import Settings

        settings = Settings()

        self._agent_id = agent_id
        self._settings = settings

        url = radicale_url or settings.RADICALE_URL
        username = radicale_username or settings.RADICALE_USERNAME
        password = radicale_password or settings.RADICALE_PASSWORD.get_secret_value()

        if not url or not username or not password:
            _MISSING_CREDENTIALS_MSG = (
                "Radicale credentials are required. "
                "Set RADICALE_URL, RADICALE_USERNAME, RADICALE_PASSWORD "
                "environment variables or pass them as constructor arguments."
            )
            raise ValueError(_MISSING_CREDENTIALS_MSG)

        default_calendar = settings.RADICALE_DEFAULT_CALENDAR
        self._caldav = CalDavClient(
            url, username, password, default_calendar=default_calendar
        )
        self._intent_parser = IntentParser(model_config=llm_model_config)

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, parsed: ParsedIntent) -> Any:
        """Route a parsed intent to the appropriate CalDavClient method."""
        op = parsed.operation
        params: dict[str, Any] = parsed.params

        logger.debug("Dispatching operation=%r params=%r", op, params)

        handler = _DISPATCH.get(op)
        if handler is None:
            raise OperationError(
                code="unknown_operation",
                message=f"Unknown operation: {op}",
            )

        if handler in _CREATE_UPDATE_HANDLERS:
            return handler(self._caldav, params, op)
        return handler(self._caldav, params)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the agent (no-op; the broker transport has been removed)."""
        logger.info("Starting CalendarAgent (agent_id=%r)", self._agent_id)

    def stop(self) -> None:
        """Stop the agent (no-op; the broker transport has been removed)."""
        logger.info("Stopping CalendarAgent (agent_id=%r)", self._agent_id)

    def __enter__(self) -> CalendarAgent:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()
