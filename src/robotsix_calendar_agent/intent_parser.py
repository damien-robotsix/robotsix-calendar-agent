"""llmio-based intent parser for calendar/contact instructions.

Converts natural-language text into a structured :class:`ParsedIntent`
with one of 8 operation types and extracted parameters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CalendarOperation(StrEnum):
    """Calendar (CalDAV) operation types."""

    LIST_EVENTS = "list_events"
    CREATE_EVENT = "create_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"


class ContactOperation(StrEnum):
    """Contacts (CardDAV) operation types."""

    LIST_CONTACTS = "list_contacts"
    CREATE_CONTACT = "create_contact"
    UPDATE_CONTACT = "update_contact"
    DELETE_CONTACT = "delete_contact"


@dataclass(kw_only=True)
class ParsedIntent:
    """Result of parsing a user instruction.

    Attributes:
        operation: The classified operation.
        params: Operation-specific arguments (dates, uids, fields, ...).
        original_text: The raw instruction string, preserved for logging.
    """

    operation: CalendarOperation | ContactOperation
    params: dict[str, Any] = field(default_factory=dict)
    original_text: str = ""


class IntentParseError(Exception):
    """Raised when intent parsing fails (llmio error or unclassifiable input)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class IntentParser:
    """Parser that uses ``robotsix-llmio`` to classify instructions.

    Args:
        model_config: Forwarded to the llmio provider for model
            selection/temperature/etc.  If ``None``, llmio defaults apply.
    """

    def __init__(self, model_config: dict[str, Any] | None = None) -> None:
        self._model_config = model_config or {}

    def parse(self, text: str) -> ParsedIntent:
        """Parse natural-language *text* into a :class:`ParsedIntent`.

        Raises:
            IntentParseError: If the llmio call fails or the model cannot
                produce a valid structured result.
        """
        try:
            from robotsix_llmio.core import get_provider, run_agent

            provider = get_provider(**self._model_config)

            # level=1 is the cheap tier with reasoning DISABLED. DeepSeek's
            # thinking mode rejects the tool_choice pydantic-ai uses for
            # structured output ("Thinking mode does not support this
            # tool_choice"), so a non-reasoning tier is required here.
            handle = provider.build_agent(
                level=1,
                system_prompt=_INTENT_SYSTEM_PROMPT,
                output_type=_IntentOutput,
            )

            def _run() -> _IntentOutput:
                # AgentHandle delegates attribute access to the wrapped
                # pydantic-ai Agent, so call run_sync on the handle directly.
                # pydantic-ai >=1.0 exposes the result on ``.output``.
                result = handle.run_sync(text)
                return result.output  # type: ignore[no-any-return]

            output = run_agent(
                handle,
                _run,
                label="intent-parse",
                what="intent parsing",
            )
            if not isinstance(output, _IntentOutput):
                _msg = f"Unexpected output type from llmio: {type(output)}"
                raise IntentParseError(_msg)

            result = ParsedIntent(
                operation=output.operation,  # type: ignore[arg-type]
                params=output.params or {},
                original_text=text,
            )
            logger.info("Parsed intent: operation=%r text=%r", result.operation, text)
            return result
        except IntentParseError as exc:
            logger.exception("Intent parse error for '%s': %s", text, exc)
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error during intent parsing for '%s': %s", text, exc
            )
            _msg = f"Intent parsing failed: {exc}"
            raise IntentParseError(_msg) from exc


# ---------------------------------------------------------------------------
# Internal pydantic model for structured output
# ---------------------------------------------------------------------------


class _IntentOutput(BaseModel):  # type: ignore[misc]
    """Structured output from the llmio model — not part of the public API."""

    operation: Literal[
        "list_events",
        "create_event",
        "update_event",
        "delete_event",
        "list_contacts",
        "create_contact",
        "update_contact",
        "delete_contact",
    ]
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters as key-value pairs.",
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_INTENT_SYSTEM_PROMPT = """\
You are an intent classifier for a calendar and contacts management agent.

Given a natural-language instruction, classify it into exactly one of these
operations and extract structured parameters:

Calendar operations:
- list_events: params = {start, end, calendar_id?}  (ISO 8601 dates)
- create_event: params = {summary, dtstart, dtend, description?, location?,calendar_id?}
- update_event: params = {uid, ...fields to update, calendar_id?}
- delete_event: params = {uid, calendar_id?}

Contacts operations:
- list_contacts: params = {addressbook_id?}
- create_contact: params = {full_name, email?, phone?, address?, addressbook_id?}
- update_contact: params = {uid, ...fields to update, addressbook_id?}
- delete_contact: params = {uid, addressbook_id?}

Rules:
- For date expressions like "next Tuesday at 3pm", compute ISO 8601 datetimes
  relative to the current date.
- For "this week", set start to Monday 00:00 and end to Sunday 23:59 of the
  current week.
- If a UID is not provided but needed (update/delete), leave it empty.
- Return only the operation and params — no extra commentary.
"""
