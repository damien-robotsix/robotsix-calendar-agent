"""CalendarAgent — agent-comm entry point for calendar/contacts management.

Wires together :class:`IntentParser`, :class:`CalDavClient`, and the
agent-comm messaging layer into a single runnable agent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
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

from .add_to_calendar_handler import (
    _event_to_dict,
    handle_add_to_calendar,
)
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
        transport: Optional transport object to wire the agent-comm
            :class:`Agent` to. When ``None`` (the default), an
            in-process :class:`Registry` is created — full backward
            compatibility. When provided (e.g. a brokered transport
            client), it is used in place of the in-process registry.

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
        transport: Any | None = None,
    ) -> None:
        import os

        from robotsix_agent_comm.sdk import (
            Agent as AgentCommAgent,
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

        if transport is None:
            from robotsix_agent_comm.transport import (
                Registry,
            )

            self._transport: Any = Registry()
        else:
            self._transport = transport

        self._agent = AgentCommAgent(agent_id, self._transport)

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
            return handle_add_to_calendar(
                self._caldav, request, body["add_to_calendar"]
            )

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


def _contact_to_dict(contact: Contact) -> dict[str, Any]:
    return {
        "uid": contact.uid,
        "full_name": contact.full_name,
        "email": contact.email,
        "phone": contact.phone,
        "address": contact.address,
        "addressbook_id": contact.addressbook_id,
    }


def _entity_op(
    client: CalDavClient,
    params: dict[str, Any],
    *,
    builder: Callable[[dict[str, Any]], Any],
    serializer: Callable[[Any], dict[str, Any]],
    create_fn: Callable[..., Any],
    update_fn: Callable[..., Any],
    id_key: str,
) -> dict[str, Any]:
    """Generic helper for create/update handlers.

    Captures the common 3-step pattern:
    1. Build domain object from params.
    2. Call client CRUD method (create if no uid, else update).
    3. Serialize result via serializer.
    """
    entity = builder(params)
    op = update_fn if "uid" in params else create_fn
    uid = params.get("uid", "")
    kwargs = {id_key: params.get(id_key, "")}
    result = op(uid, entity, **kwargs) if op is update_fn else op(entity, **kwargs)
    return serializer(result)


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
    return _entity_op(
        client,
        params,
        builder=_build_event,
        serializer=_event_to_dict,
        create_fn=client.create_event,
        update_fn=client.update_event,
        id_key="calendar_id",
    )


def _handle_update_event(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, Any]:
    return _entity_op(
        client,
        params,
        builder=_build_event,
        serializer=_event_to_dict,
        create_fn=client.create_event,
        update_fn=client.update_event,
        id_key="calendar_id",
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
    return _entity_op(
        client,
        params,
        builder=_build_contact,
        serializer=_contact_to_dict,
        create_fn=client.create_contact,
        update_fn=client.update_contact,
        id_key="addressbook_id",
    )


def _handle_update_contact(
    client: CalDavClient, params: dict[str, Any]
) -> dict[str, Any]:
    return _entity_op(
        client,
        params,
        builder=_build_contact,
        serializer=_contact_to_dict,
        create_fn=client.create_contact,
        update_fn=client.update_contact,
        id_key="addressbook_id",
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
