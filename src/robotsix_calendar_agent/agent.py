"""CalendarAgent — agent-comm entry point for calendar/contacts management.

Wires together :class:`IntentParser`, :class:`CalDavClient`, and the
agent-comm messaging layer into a single runnable agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from .caldav_client import CalDavClient, CalendarEvent, Contact, OperationError
from .intent_parser import IntentParseError, IntentParser, ParsedIntent

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

        instruction: str | None = body.get("instruction")
        if not instruction:
            return Error.to(
                request,
                code="missing_instruction",
                message="Request body must contain an 'instruction' key.",
            )

        try:
            parsed: ParsedIntent = self._intent_parser.parse(instruction)
        except IntentParseError as exc:
            return Error.to(request, code="parse_error", message=str(exc))

        try:
            result = self._dispatch(parsed)
            return Response.to(request, body={"result": result})
        except OperationError as exc:
            return Error.to(request, code=exc.code, message=exc.message)
        except Exception as exc:
            return Error.to(request, code="internal_error", message=str(exc))

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, parsed: ParsedIntent) -> Any:
        """Route a parsed intent to the appropriate CalDavClient method."""
        op = parsed.operation
        params: dict[str, Any] = parsed.params

        # -- Calendar operations --
        if op == "list_events":
            return [
                _event_to_dict(e)
                for e in self._caldav.list_events(
                    start=params.get("start", ""),
                    end=params.get("end", ""),
                    calendar_id=params.get("calendar_id", ""),
                )
            ]

        if op == "create_event":
            event = CalendarEvent(
                summary=params.get("summary", ""),
                description=params.get("description", ""),
                location=params.get("location", ""),
                dtstart=params.get("dtstart", ""),
                dtend=params.get("dtend", ""),
                calendar_id=params.get("calendar_id", ""),
            )
            return _event_to_dict(
                self._caldav.create_event(
                    event, calendar_id=params.get("calendar_id", "")
                )
            )

        if op == "update_event":
            event = CalendarEvent(
                summary=params.get("summary", ""),
                description=params.get("description", ""),
                location=params.get("location", ""),
                dtstart=params.get("dtstart", ""),
                dtend=params.get("dtend", ""),
                calendar_id=params.get("calendar_id", ""),
            )
            return _event_to_dict(
                self._caldav.update_event(
                    uid=params.get("uid", ""),
                    event=event,
                    calendar_id=params.get("calendar_id", ""),
                )
            )

        if op == "delete_event":
            self._caldav.delete_event(
                uid=params.get("uid", ""),
                calendar_id=params.get("calendar_id", ""),
            )
            return {"deleted": True}

        # -- Contacts operations --
        if op == "list_contacts":
            return [
                _contact_to_dict(c)
                for c in self._caldav.list_contacts(
                    addressbook_id=params.get("addressbook_id", ""),
                )
            ]

        if op == "create_contact":
            contact = Contact(
                full_name=params.get("full_name", ""),
                email=params.get("email", ""),
                phone=params.get("phone", ""),
                address=params.get("address", ""),
                addressbook_id=params.get("addressbook_id", ""),
            )
            return _contact_to_dict(
                self._caldav.create_contact(
                    contact,
                    addressbook_id=params.get("addressbook_id", ""),
                )
            )

        if op == "update_contact":
            contact = Contact(
                full_name=params.get("full_name", ""),
                email=params.get("email", ""),
                phone=params.get("phone", ""),
                address=params.get("address", ""),
                addressbook_id=params.get("addressbook_id", ""),
            )
            return _contact_to_dict(
                self._caldav.update_contact(
                    uid=params.get("uid", ""),
                    contact=contact,
                    addressbook_id=params.get("addressbook_id", ""),
                )
            )

        if op == "delete_contact":
            self._caldav.delete_contact(
                uid=params.get("uid", ""),
                addressbook_id=params.get("addressbook_id", ""),
            )
            return {"deleted": True}

        raise OperationError(
            code="unknown_operation",
            message=f"Unknown operation: {op}",
        )

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the agent-comm transport and register the endpoint."""
        self._agent.start()

    def stop(self) -> None:
        """Stop the agent-comm transport and unregister."""
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
# serialization helpers
# ---------------------------------------------------------------------------


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
