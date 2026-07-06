"""CalendarAgent — calendar/contacts management agent.

Wires together :class:`IntentParser`, :class:`CalDavClient` into a
single runnable agent.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from opentelemetry import trace

try:
    from robotsix_llmio.core import setup_langfuse_tracing  # pragma: no cover

    setup_langfuse_tracing()
except ImportError:  # pragma: no cover
    pass

from .add_to_calendar_handler import _event_to_dict
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

logger = logging.getLogger(__name__)

_tracer = trace.get_tracer(__name__)

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

        with _tracer.start_as_current_span("agent.dispatch") as span:
            span.set_attribute("agent.operation", op)
            span.set_attribute("agent.agent_id", self._agent_id)
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


def _task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "uid": task.uid,
        "summary": task.summary,
        "description": task.description,
        "dtstart": task.dtstart,
        "due": task.due,
        "status": task.status,
        "calendar_id": task.calendar_id,
    }


def _entity_op(
    params: dict[str, Any],
    *,
    builder: Callable[[dict[str, Any]], Any],
    serializer: Callable[[Any], dict[str, Any]],
    create_fn: Callable[..., Any],
    update_fn: Callable[..., Any],
    id_key: str,
    operation: str | None = None,
) -> dict[str, Any]:
    """Generic helper for create/update handlers.

    Captures the common 3-step pattern:
    1. Build domain object from params.
    2. Call client CRUD method — create unless *operation* starts with
       ``"update"`` (dispatch is operation-based, never uid-based).
    3. Serialize result via serializer.
    """
    entity = builder(params)
    if operation and operation.startswith("update"):
        uid = params.get("uid", "")
        if not uid:
            raise OperationError(
                code="missing_uid",
                message="A UID is required to update, but none was provided.",
            )
        kwargs = {id_key: params.get(id_key, "")}
        result = update_fn(uid, entity, **kwargs)
    else:
        kwargs = {id_key: params.get(id_key, "")}
        result = create_fn(entity, **kwargs)
    return serializer(result)


def _delete_entity_op(
    params: dict[str, Any],
    *,
    delete_fn: Callable[..., None],
    id_key: str,
) -> dict[str, bool]:
    """Generic helper for delete handlers.

    Captures the common pattern:
    1. Validate uid is present and non-empty.
    2. Call client delete method.
    3. Return confirmation dict.
    """
    uid = params.get("uid", "")
    if not uid:
        raise OperationError(
            code="missing_uid",
            message="A UID is required to delete, but none was provided.",
        )
    kwargs: dict[str, Any] = {id_key: params.get(id_key, "")}
    delete_fn(uid=uid, **kwargs)
    return {"deleted": True}


def _handle_list_events(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _event_to_dict(e)
        for e in client.list_events(
            start=params.get("start", ""),
            end=params.get("end", ""),
            calendar_id=params.get("calendar_id", ""),
        )
    ]


def _handle_list_tasks(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _task_to_dict(t)
        for t in client.list_tasks(
            calendar_id=params.get("calendar_id", ""),
        )
    ]


def _handle_create_or_update_event(
    client: CalDavClient,
    params: dict[str, Any],
    operation: str = "",
) -> dict[str, Any]:
    return _entity_op(
        params,
        builder=_build_event,
        serializer=_event_to_dict,
        create_fn=client.create_event,
        update_fn=client.update_event,
        id_key="calendar_id",
        operation=operation,
    )


def _handle_list_calendars(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[str]:
    """Return the names of the user's available calendars."""
    return client.list_calendars()


def _handle_delete_event(
    client: CalDavClient,
    params: dict[str, Any],
) -> dict[str, bool]:
    return _delete_entity_op(
        params, delete_fn=client.delete_event, id_key="calendar_id"
    )


def _handle_list_contacts(
    client: CalDavClient,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _contact_to_dict(c)
        for c in client.list_contacts(addressbook_id=params.get("addressbook_id", ""))
    ]


def _handle_create_or_update_contact(
    client: CalDavClient,
    params: dict[str, Any],
    operation: str = "",
) -> dict[str, Any]:
    return _entity_op(
        params,
        builder=_build_contact,
        serializer=_contact_to_dict,
        create_fn=client.create_contact,
        update_fn=client.update_contact,
        id_key="addressbook_id",
        operation=operation,
    )


def _handle_delete_contact(
    client: CalDavClient,
    params: dict[str, Any],
) -> dict[str, bool]:
    return _delete_entity_op(
        params, delete_fn=client.delete_contact, id_key="addressbook_id"
    )


_CREATE_UPDATE_HANDLERS: set[Callable[..., Any]] = {
    _handle_create_or_update_event,
    _handle_create_or_update_contact,
}

_DISPATCH: dict[str, Callable[..., Any]] = {
    "list_events": _handle_list_events,
    "list_calendars": _handle_list_calendars,
    "create_event": _handle_create_or_update_event,
    "update_event": _handle_create_or_update_event,
    "delete_event": _handle_delete_event,
    "list_tasks": _handle_list_tasks,
    "list_contacts": _handle_list_contacts,
    "create_contact": _handle_create_or_update_contact,
    "update_contact": _handle_create_or_update_contact,
    "delete_contact": _handle_delete_contact,
}


def _summarize_item(item: dict[str, Any]) -> str:
    """One-line human summary of an event, task, or contact dict."""
    if isinstance(item, str):
        return item
    if "due" in item or "status" in item:  # task (VTODO)
        parts = [str(item.get("summary") or "(untitled)")]
        if item.get("due"):
            parts.append(f"due {item['due']}")
        if item.get("status"):
            parts.append(f"[{item['status']}]")
        line = " ".join(parts)
        return f"{line} [uid={item['uid']}]" if item.get("uid") else line
    if "summary" in item or "dtstart" in item:  # event
        parts = [str(item.get("summary") or "(untitled)")]
        if item.get("dtstart"):
            parts.append(f"at {item['dtstart']}")
        if item.get("location"):
            parts.append(f"({item['location']})")
        line = " ".join(parts)
        return f"{line} [uid={item['uid']}]" if item.get("uid") else line
    if "full_name" in item or "email" in item:  # contact
        name = str(item.get("full_name") or "(no name)")
        return f"{name} <{item['email']}>" if item.get("email") else name
    return json.dumps(item, default=str)


def _render_reply(operation: str, result: Any) -> str:
    """Render a human-readable reply string from a dispatch *result*.

    Generic consumers (e.g. robotsix-chat) read the reply via
    ``reply_text``, which looks for the ``"reply"`` key; the structured
    ``"result"`` is retained for programmatic consumers. Without this, those
    consumers see an empty reply and fall back to their default message.
    """
    if isinstance(result, dict) and result.get("deleted") is True:
        return "Done — the item was deleted."
    if isinstance(result, list):
        if not result:
            noun = (
                "events"
                if "event" in operation
                else "calendars"
                if "calendar" in operation
                else "tasks"
                if "task" in operation
                else "contacts"
                if "contact" in operation
                else "items"
            )
            return f"No {noun} found."
        lines = "\n".join(f"- {_summarize_item(i)}" for i in result)
        return f"Found {len(result)}:\n{lines}"
    if isinstance(result, dict):
        verb = (
            "Updated"
            if operation.startswith("update")
            else "Created"
            if operation.startswith("create")
            else "Result"
        )
        return f"{verb}: {_summarize_item(result)}"
    return str(result)


_DISPATCH_KEYS = set(_DISPATCH)
_ENUM_VALUES = (
    {m.value for m in CalendarOperation}
    | {m.value for m in ContactOperation}
    | {m.value for m in TaskOperation}
)
assert _DISPATCH_KEYS == _ENUM_VALUES, (  # nosec B101 — import-time invariant check
    f"Mismatch: extra in dict={_DISPATCH_KEYS - _ENUM_VALUES}, "
    f"missing={_ENUM_VALUES - _DISPATCH_KEYS}"
)
