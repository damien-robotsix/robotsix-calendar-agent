"""Structured add-to-calendar handler — no LLM intent parsing.

Handles ``add_to_calendar`` request payloads from auto-mail, validating
and creating calendar events directly via the CalDAV client.
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


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


def handle_add_to_calendar(
    caldav_client: Any,
    request: Any,
    payload: dict[str, Any],
) -> Any:
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
                ERROR_MISSING_SUBJECT,
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
                ERROR_MISSING_DATES,
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

    event = CalendarEvent(
        summary=subject.strip(),
        description=description or "",
        location=location or "",
        dtstart=suggested_dtstart,
        dtend=suggested_dtend,
    )

    try:
        created = caldav_client.create_event(event)
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
