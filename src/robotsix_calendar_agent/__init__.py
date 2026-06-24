"""robotsix_calendar_agent — agent-comm calendar and contacts agent for Radicale.

This package provides a calendar and contacts management agent driven by
the ``robotsix-agent-comm`` messaging system.  It parses natural-language
instructions via ``robotsix-llmio`` and executes CalDAV/CardDAV operations
against a Radicale server.
"""

from __future__ import annotations

from .agent import CalendarAgent
from .caldav_client import (
    CalDavClient,
    CalendarEvent,
    Contact,
    OperationError,
    Task,
)
from .intent_parser import (
    CalendarOperation,
    ContactOperation,
    IntentParseError,
    IntentParser,
    ParsedIntent,
    TaskOperation,
)

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
    "__version__",
]

__version__ = "0.1.0"
