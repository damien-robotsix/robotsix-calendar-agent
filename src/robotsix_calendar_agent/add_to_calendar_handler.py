"""Structured add-to-calendar handler.

Handles ``add_to_calendar`` request payloads from auto-mail, validating
and creating calendar events via the CalDAV client. Concrete start/end
datetimes are taken from explicit ``suggested_dt*`` fields when present,
otherwise resolved from the forwarded email context via the LLM intent
parser.
"""

from __future__ import annotations

import logging
from typing import Any

from .caldav_client import CalendarEvent, OperationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error codes used in validation responses — shared with tests.
# ---------------------------------------------------------------------------
ERROR_MISSING_SUBJECT = "missing_subject"
ERROR_MISSING_DATES = "missing_dates"
ERROR_INVALID_DATES = "invalid_dates"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_error_body(code: str, message: str, correlation_id: str) -> dict[str, Any]:
    """Build the error-shaped body for add-to-calendar error responses."""
    return {
        "error": {"code": code, "message": message},
        "correlation_id": correlation_id,
    }


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


def _build_resolution_instruction(
    subject: str,
    body_text: str,
    email_date: str,
    extracted_dates: list[str],
) -> str:
    """Build a natural-language instruction for the intent parser.

    auto-mail forwards the raw email context (subject, body, regex-extracted
    date strings) rather than concrete start/end datetimes. This phrases that
    context as a ``create_event`` instruction so the LLM intent parser can
    resolve ISO 8601 ``dtstart``/``dtend`` values.
    """
    lines = [
        "Create a calendar event for the following email.",
        f"Email subject: {subject}",
    ]
    if email_date:
        lines.append(f"Email date: {email_date}")
    if extracted_dates:
        lines.append("Date/time references found: " + ", ".join(extracted_dates))
    if body_text:
        lines.append("Email body:")
        lines.append(body_text)
    lines.append(
        "Resolve a concrete start and end datetime in ISO 8601. If no end "
        "time is stated, default the end to one hour after the start."
    )
    return "\n".join(lines)


def _explicit_dates(payload: dict[str, Any]) -> tuple[str, str] | None:
    """Return ``(dtstart, dtend)`` when the payload carries both as non-empty
    ISO strings, else ``None`` (so the caller falls back to LLM resolution)."""
    ds = payload.get("suggested_dtstart")
    de = payload.get("suggested_dtend")
    if isinstance(ds, str) and ds and isinstance(de, str) and de:
        return ds, de
    return None


def _resolve_dates_via_llm(
    intent_parser: Any,
    payload: dict[str, Any],
) -> tuple[str, str] | None:
    """Resolve ``(dtstart, dtend)`` from the email context via *intent_parser*.

    Returns ``None`` when the parser is unavailable, errors, or cannot produce
    a ``create_event`` intent carrying non-empty ISO date strings — the caller
    then surfaces ``ERROR_MISSING_DATES``.
    """
    if intent_parser is None:
        return None
    instruction = _build_resolution_instruction(
        str(payload.get("subject", "")),
        str(payload.get("body_text", "") or ""),
        str(payload.get("email_date", "") or ""),
        list(payload.get("extracted_dates") or []),
    )
    try:
        parsed = intent_parser.parse(instruction)
    except Exception:  # noqa: BLE001 — any parse failure degrades to missing_dates
        logger.exception("LLM date resolution failed")
        return None

    if str(getattr(parsed, "operation", "")) != "create_event":
        return None
    params = getattr(parsed, "params", None) or {}
    dtstart = params.get("dtstart")
    dtend = params.get("dtend")
    if isinstance(dtstart, str) and dtstart and isinstance(dtend, str) and dtend:
        return dtstart, dtend
    return None


# ---------------------------------------------------------------------------
# handler helpers
# ---------------------------------------------------------------------------


def _validate_add_to_calendar_payload(
    payload: dict[str, Any],
    request: Any,
) -> tuple[str, str, str, str] | Any:
    """Validate the add-to-calendar payload and extract core fields.

    Returns ``(subject, description, location, correlation_id)`` on success,
    or a :class:`~robotsix_agent_comm.protocol.Response` on validation
    failure.
    """
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
    description = payload.get("description")
    location = payload.get("location")
    correlation_id: str = payload.get("correlation_id", "")

    if not subject or not isinstance(subject, str) or not subject.strip():
        return Response.to(
            request,
            body=_build_error_body(
                ERROR_MISSING_SUBJECT,
                "Subject is required and must be a non-empty string.",
                correlation_id,
            ),
        )

    return subject.strip(), description or "", location or "", correlation_id


def _resolve_event_dates(
    payload: dict[str, Any],
    intent_parser: Any,
) -> tuple[str, str] | None:
    """Resolve event start/end datetimes from the payload.

    Prefers explicit ``suggested_dtstart``/``suggested_dtend`` fields;
    falls back to LLM-based resolution via *intent_parser*.  Returns
    ``None`` when dates cannot be determined.
    """
    return _explicit_dates(payload) or _resolve_dates_via_llm(intent_parser, payload)


def _create_calendar_event(
    caldav_client: Any,
    request: Any,
    subject: str,
    description: str,
    location: str,
    dtstart_str: str,
    dtend_str: str,
    correlation_id: str,
) -> tuple[Any, Any | None]:
    """Create a calendar event via the CalDAV client.

    Returns ``(created_event, None)`` on success, or
    ``(None, error_response)`` when creation fails.
    """
    from robotsix_agent_comm.protocol import Response

    event = CalendarEvent(
        summary=subject,
        description=description,
        location=location,
        dtstart=dtstart_str,
        dtend=dtend_str,
    )

    try:
        created = caldav_client.create_event(event)
    except OperationError as exc:
        logger.exception("CalDAV error creating event '%s': %s", subject, exc)
        return None, Response.to(
            request,
            body=_build_error_body(exc.code, exc.message, correlation_id),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Internal error creating event '%s': %s", subject, exc)
        return None, Response.to(
            request,
            body=_build_error_body(
                "internal_error",
                f"Unexpected error: {exc}",
                correlation_id,
            ),
        )

    return created, None


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


def handle_add_to_calendar(
    caldav_client: Any,
    request: Any,
    payload: dict[str, Any],
    *,
    intent_parser: Any | None = None,
) -> Any:
    """Handle a structured add-to-calendar request from auto-mail.

    Validates the payload, creates a :class:`CalendarEvent` via
    :meth:`CalDavClient.create_event`, and returns a correlated
    :class:`Response` — always carrying the ``correlation_id``
    from the request, whether successful or not.

    When the payload carries explicit ``suggested_dtstart``/``suggested_dtend``
    ISO strings, they are used directly (LLM-free path). Otherwise — auto-mail's
    usual case, which forwards only the raw email context — *intent_parser*
    (when provided) resolves concrete start/end datetimes from the subject,
    body, and extracted date references.
    """
    import datetime

    from robotsix_agent_comm.protocol import Response

    # -- validation ---------------------------------------------------

    result = _validate_add_to_calendar_payload(payload, request)
    if not isinstance(result, tuple):
        return result  # error Response
    subject, description, location, correlation_id = result

    # -- date resolution ----------------------------------------------

    dates = _resolve_event_dates(payload, intent_parser)
    if dates is None:
        return Response.to(
            request,
            body=_build_error_body(
                ERROR_MISSING_DATES,
                "Could not determine event start/end times: provide "
                "suggested_dtstart and suggested_dtend, or email content "
                "the calendar agent can resolve a date from.",
                correlation_id,
            ),
        )
    dtstart_str, dtend_str = dates

    # -- ISO 8601 parsing + time-ordering -----------------------------

    try:
        dtstart = datetime.datetime.fromisoformat(dtstart_str)
        dtend = datetime.datetime.fromisoformat(dtend_str)
    except (ValueError, TypeError):
        return Response.to(
            request,
            body=_build_error_body(
                ERROR_INVALID_DATES,
                "Cannot parse one or both date strings as ISO 8601.",
                correlation_id,
            ),
        )

    if dtend <= dtstart:
        return Response.to(
            request,
            body=_build_error_body(
                ERROR_INVALID_DATES,
                "End time must be after start time.",
                correlation_id,
            ),
        )

    # -- event creation -----------------------------------------------

    created, error_resp = _create_calendar_event(
        caldav_client,
        request,
        subject,
        description,
        location,
        dtstart_str,
        dtend_str,
        correlation_id,
    )
    if error_resp is not None:
        return error_resp

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
