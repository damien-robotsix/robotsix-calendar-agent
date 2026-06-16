"""CalendarAgent — agent-comm entry point for calendar/contacts management.

Wires together :class:`IntentParser`, :class:`CalDavClient`, and the
agent-comm messaging layer into a single runnable agent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

try:
    from robotsix_llmio.core import setup_langfuse_tracing  # pragma: no cover
    from robotsix_llmio.logging import setup_logging  # pragma: no cover

    setup_logging(loggers=["robotsix_calendar_agent"])
    setup_langfuse_tracing()
except ImportError:  # pragma: no cover
    pass

if TYPE_CHECKING:
    pass

from .caldav_client import CalDavClient, CalendarEvent, Contact, OperationError
from .intent_parser import IntentParseError, IntentParser, ParsedIntent

logger = logging.getLogger(__name__)

__all__ = ["CalendarAgent"]


class CalendarAgent:
    """Top-level agent that processes calendar/contact instructions.

    Creates a :class:`CalDavClient`, :class:`IntentParser`, and an
    agent-comm :class:`Agent`, then registers an ``on_request`` handler
    that parses intent, dispatches to CalDAV/CardDAV, and returns a
    correlated response.

    Args:
        agent_id: Agent-comm agent ID (default ``"calendar"``).
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
        import os

        from robotsix_agent_comm.sdk import (
            Agent as AgentCommAgent,
        )
        from robotsix_agent_comm.transport import (
            Registry,
        )

        self._agent_id = agent_id

        url = radicale_url or os.environ.get("RADICALE_URL", "")
        username = radicale_username or os.environ.get("RADICALE_USERNAME", "")
        password = radicale_password or os.environ.get("RADICALE_PASSWORD", "")

        if not url or not username or not password:
            raise ValueError(
                "Radicale credentials are required. "
                "Set RADICALE_URL, RADICALE_USERNAME, RADICALE_PASSWORD "
                "environment variables or pass them as constructor arguments."
            )

        self._caldav = CalDavClient(url, username, password)
        self._intent_parser = IntentParser(model_config=llm_model_config)

        self._registry = Registry()
        self._agent = AgentCommAgent(agent_id, self._registry)

        self._agent.on_request(self._handle_request)

    # ------------------------------------------------------------------
    # request handler
    # ------------------------------------------------------------------

    def _handle_request(self, request: Any) -> Any:
        """Handle an incoming agent-comm request.

        Extracts the ``"instruction"`` from the request body, parses
        intent, dispatches to the CalDAV/CardDAV client, and returns
        a correlated response or error.
        """
        from robotsix_agent_comm.protocol import (
            Error,
            Response,
        )

        body: dict[str, Any] = request.body or {}

        if "add_to_calendar" in body:
            return self._handle_add_to_calendar(request, body["add_to_calendar"])

        instruction: str | None = body.get("instruction")
        if not instruction:
            logger.error("Request missing 'instruction' key: %s", body)
            return Error.to(
                request,
                code="missing_instruction",
                message="Request body must contain an 'instruction' key.",
            )

        logger.info("Processing instruction: %s", instruction)

        try:
            parsed: ParsedIntent = self._intent_parser.parse(instruction)
        except IntentParseError as exc:
            logger.error("Intent parse error for '%s': %s", instruction, exc)
            return Error.to(request, code="parse_error", message=str(exc))

        try:
            result = self._dispatch(parsed)
            return Response.to(request, body={"result": result})
        except OperationError as exc:
            logger.error(
                "Operation error for '%s' (op=%s): %s",
                instruction,
                parsed.operation,
                exc,
            )
            return Error.to(request, code=exc.code, message=exc.message)
        except Exception as exc:
            logger.error(
                "Internal error for '%s' (op=%s): %s",
                instruction,
                parsed.operation,
                exc,
            )
            return Error.to(request, code="internal_error", message=str(exc))

    # ------------------------------------------------------------------
    # add-to-calendar (structured, no LLM)
    # ------------------------------------------------------------------

    def _handle_add_to_calendar(self, request: Any, payload: dict[str, Any]) -> Any:
        """Handle a structured add-to-calendar request from auto-mail.

        Validates the payload, creates a :class:`CalendarEvent` via
        :meth:`CalDavClient.create_event`, and returns a correlated
        :class:`Response` — always carrying the ``correlation_id``
        from the request, whether successful or not.
        """
        import datetime

        from robotsix_agent_comm.protocol import Response

        if not isinstance(payload, dict):
            return Response.to(
                request,
                body=_build_error_body(
                    "internal_error",
                    "add_to_calendar payload must be a dictionary.",
                    "",
                ),
            )

        subject = payload.get("subject")
        _ = payload.get("body_text")  # extracted per spec, unused in LLM-free path
        suggested_dtstart = payload.get("suggested_dtstart")
        suggested_dtend = payload.get("suggested_dtend")
        description = payload.get("description")
        location = payload.get("location")
        correlation_id: str = payload.get("correlation_id", "")

        # -- validation ---------------------------------------------------

        if not subject or not isinstance(subject, str) or not subject.strip():
            return Response.to(
                request,
                body=_build_error_body(
                    "missing_subject",
                    "Subject is required and must be a non-empty string.",
                    correlation_id,
                ),
            )

        if (
            not suggested_dtstart
            or not suggested_dtend
            or not isinstance(suggested_dtstart, str)
            or not isinstance(suggested_dtend, str)
        ):
            return Response.to(
                request,
                body=_build_error_body(
                    "missing_dates",
                    "Both suggested_dtstart and suggested_dtend are required "
                    "and must be non-empty strings.",
                    correlation_id,
                ),
            )

        try:
            dtstart = datetime.datetime.fromisoformat(suggested_dtstart)
            dtend = datetime.datetime.fromisoformat(suggested_dtend)
        except (ValueError, TypeError):
            return Response.to(
                request,
                body=_build_error_body(
                    "invalid_dates",
                    "Cannot parse one or both date strings as ISO 8601.",
                    correlation_id,
                ),
            )

        if dtend <= dtstart:
            return Response.to(
                request,
                body=_build_error_body(
                    "invalid_dates",
                    "End time must be after start time.",
                    correlation_id,
                ),
            )

        # -- event creation -----------------------------------------------

        event = CalendarEvent(
            summary=subject.strip(),
            description=description or "",
            location=location or "",
            dtstart=suggested_dtstart,
            dtend=suggested_dtend,
        )

        try:
            created = self._caldav.create_event(event)
        except OperationError as exc:
            logger.error("CalDAV error creating event '%s': %s", subject, exc)
            return Response.to(
                request,
                body=_build_error_body(exc.code, exc.message, correlation_id),
            )
        except Exception as exc:
            logger.error("Internal error creating event '%s': %s", subject, exc)
            return Response.to(
                request,
                body=_build_error_body(
                    "internal_error",
                    f"Unexpected error: {exc}",
                    correlation_id,
                ),
            )

        # -- success response ---------------------------------------------

        event_dict = _event_to_dict(created)
        confirmation_text = (
            f"Created event '{created.summary}' on "
            f"{dtstart.strftime('%b %d, %Y at %I:%M %p')}"
        )

        logger.info("Created event '%s' (uid=%s)", created.summary, created.uid)

        return Response.to(
            request,
            body={
                "result": {
                    "status": "created",
                    "event": event_dict,
                    "confirmation_text": confirmation_text,
                },
                "correlation_id": correlation_id,
            },
        )

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

        return handler(self._caldav, params)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the agent-comm transport and register the endpoint."""
        logger.info("Starting CalendarAgent (agent_id=%r)", self._agent_id)
        self._agent.start()

    def stop(self) -> None:
        """Stop the agent-comm transport and unregister."""
        logger.info("Stopping CalendarAgent (agent_id=%r)", self._agent_id)
        self._agent.stop()

    def close(self) -> None:
        """Alias for :meth:`stop`."""
        self.stop()

    def __enter__(self) -> CalendarAgent:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# dispatch infrastructure
# ---------------------------------------------------------------------------


def _build_event(params: dict[str, Any]) -> CalendarEvent:
    """Build a :class:`CalendarEvent` from parsed intent *params*."""
    return CalendarEvent(
        summary=params.get("summary", ""),
        description=params.get("description", ""),
        location=params.get("location", ""),
        dtstart=params.get("dtstart", ""),
        dtend=params.get("dtend", ""),
        calendar_id=params.get("calendar_id", ""),
    )


def _build_contact(params: dict[str, Any]) -> Contact:
    """Build a :class:`Contact` from parsed intent *params*."""
    return Contact(
        full_name=params.get("full_name", ""),
        email=params.get("email", ""),
        phone=params.get("phone", ""),
        address=params.get("address", ""),
        addressbook_id=params.get("addressbook_id", ""),
    )


def _event_to_dict(event: CalendarEvent) -> dict[str, Any]:
    return {
        "uid": event.uid,
        "summary": event.summary,
        "description": event.description,
        "location": event.location,
        "dtstart": event.dtstart,
        "dtend": event.dtend,
        "calendar_id": event.calendar_id,
    }


def _contact_to_dict(contact: Contact) -> dict[str, Any]:
    return {
        "uid": contact.uid,
        "full_name": contact.full_name,
        "email": contact.email,
        "phone": contact.phone,
        "address": contact.address,
        "addressbook_id": contact.addressbook_id,
    }


def _build_error_body(code: str, message: str, correlation_id: str) -> dict[str, Any]:
    """Build the error-shaped body for add-to-calendar error responses."""
    return {
        "error": {"code": code, "message": message},
        "correlation_id": correlation_id,
    }


def _handle_list_events(
    client: CalDavClient, params: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        _event_to_dict(e)
        for e in client.list_events(
            start=params.get("start", ""),
            end=params.get("end", ""),
            calendar_id=params.get("calendar_id", ""),
        )
    ]


def _handle_create_event(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, Any]:
    event = _build_event(params)
    return _event_to_dict(
        client.create_event(event, calendar_id=params.get("calendar_id", ""))
    )


def _handle_update_event(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, Any]:
    event = _build_event(params)
    return _event_to_dict(
        client.update_event(
            uid=params.get("uid", ""),
            event=event,
            calendar_id=params.get("calendar_id", ""),
        )
    )


def _handle_delete_event(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, bool]:
    client.delete_event(
        uid=params.get("uid", ""),
        calendar_id=params.get("calendar_id", ""),
    )
    return {"deleted": True}


def _handle_list_contacts(
    client: CalDavClient, params: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        _contact_to_dict(c)
        for c in client.list_contacts(addressbook_id=params.get("addressbook_id", ""))
    ]


def _handle_create_contact(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, Any]:
    contact = _build_contact(params)
    return _contact_to_dict(
        client.create_contact(contact, addressbook_id=params.get("addressbook_id", ""))
    )


def _handle_update_contact(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, Any]:
    contact = _build_contact(params)
    return _contact_to_dict(
        client.update_contact(
            uid=params.get("uid", ""),
            contact=contact,
            addressbook_id=params.get("addressbook_id", ""),
        )
    )


def _handle_delete_contact(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, bool]:
    client.delete_contact(
        uid=params.get("uid", ""),
        addressbook_id=params.get("addressbook_id", ""),
    )
    return {"deleted": True}


_DISPATCH = {
    "list_events": _handle_list_events,
    "create_event": _handle_create_event,
    "update_event": _handle_update_event,
    "delete_event": _handle_delete_event,
    "list_contacts": _handle_list_contacts,
    "create_contact": _handle_create_contact,
    "update_contact": _handle_update_contact,
    "delete_contact": _handle_delete_contact,
}
