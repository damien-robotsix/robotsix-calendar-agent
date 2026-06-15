"""robotsix_calendar_agent — agent-comm calendar and contacts agent for Radicale.

This package provides a calendar and contacts management agent driven by
the ``robotsix-agent-comm`` messaging system.  It parses natural-language
instructions via ``robotsix-llmio`` and executes CalDAV/CardDAV operations
against a Radicale server.
"""

from __future__ import annotations

from .agent import CalendarAgent
from .caldav_client import CalDavClient, CalendarEvent, Contact, OperationError
from .intent_parser import (
    CalendarOperation,
    ContactOperation,
    IntentParser,
    ParsedIntent,
)

__all__ = [
    "CalDavClient",
    "CalendarAgent",
    "CalendarEvent",
    "CalendarOperation",
    "Contact",
    "ContactOperation",
    "IntentParser",
    "OperationError",
    "ParsedIntent",
    "__version__",
]

__version__ = "0.1.0"
