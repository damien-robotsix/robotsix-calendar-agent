"""robotsix_calendar_agent — agent-comm calendar and contacts agent for Radicale.

This package provides a calendar and contacts management agent driven by
the ``robotsix-agent-comm`` messaging system.  It parses natural-language
instructions via ``robotsix-llmio`` and executes CalDAV/CardDAV operations
against a Radicale server.
"""

from __future__ import annotations

from .agent import (  # noqa: F401 — re-exports for package namespace
    CalDavClient,
    CalendarAgent,
    CalendarEvent,
    CalendarOperation,
    Contact,
    ContactOperation,
    IntentParseError,
    IntentParser,
    OperationError,
    ParsedIntent,
    Task,
    TaskOperation,
)
from .agent import __all__ as _agent_all

__all__ = [*_agent_all, "__version__"]

__version__ = "0.1.0"
