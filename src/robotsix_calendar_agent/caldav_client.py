"""CalDAV/CardDAV client wrapper for Radicale.

Typed, self-contained module wrapping the ``caldav`` library.
All caldav-specific exceptions are converted to :class:`OperationError`.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import tenacity
from tenacity import (
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

_F = TypeVar("_F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)

__all__ = [
    "CalDavClient",
    "CalendarEvent",
    "Contact",
    "OperationError",
    "Task",
]


class OperationError(Exception):
    """Raised when a CalDAV/CardDAV operation fails.

    Attributes:
        code: Machine-readable error code (e.g. ``"not_found"``,
            ``"auth_failed"``, ``"caldav_error"``).
        message: Human-readable error description.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(kw_only=True)
class CalendarEvent:
    """Calendar event data transferred to/from the CalDAV server.

    Attributes:
        uid: Server-assigned unique identifier (empty for new events).
        summary: Short summary / title.
        description: Longer description (optional).
        location: Event location (optional).
        dtstart: Start time in ISO 8601 format.
        dtend: End time in ISO 8601 format.
        calendar_id: Calendar name the event belongs to (optional).
    """

    uid: str = ""
    summary: str
    description: str = ""
    location: str = ""
    dtstart: str  # ISO 8601
    dtend: str  # ISO 8601
    calendar_id: str = ""


@dataclass(kw_only=True)
class Task:
    """Represents a single VTODO task from a CalDAV calendar.

    Attributes:
        uid: Server-assigned unique identifier (empty for new tasks).
        summary: Short summary / title.
        description: Longer description (optional).
        dtstart: When the task starts (optional, ISO 8601).
        due: Task due date/time (VTODO DUE field, optional, ISO 8601).
        status: Task status — e.g. NEEDS-ACTION, IN-PROCESS, COMPLETED,
            CANCELLED.
        calendar_id: Calendar name the task belongs to (optional).
    """

    uid: str = ""
    summary: str
    description: str = ""
    dtstart: str = ""  # ISO 8601
    due: str = ""  # ISO 8601 — VTODO DUE field
    status: str = ""  # e.g. NEEDS-ACTION
    calendar_id: str = ""


@dataclass(kw_only=True)
class Contact:
    """Contact data transferred to/from the CardDAV server.

    Attributes:
        uid: Server-assigned unique identifier (empty for new contacts).
        full_name: Display name.
        email: Email address (optional).
        phone: Phone number (optional).
        address: Postal address (optional).
        addressbook_id: Address book name the contact belongs to (optional).
    """

    uid: str = ""
    full_name: str
    email: str = ""
    phone: str = ""
    address: str = ""
    addressbook_id: str = ""


def _is_transient_exception(exc: BaseException) -> bool:
    """Return True for exceptions that may succeed on retry."""
    msg = str(exc).lower()
    # Connection-level / timeout errors from requests/httpx
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    # Socket-level errors wrapped in generic Exception by caldav
    return any(
        word in msg
        for word in (
            "connection refused",
            "connection reset",
            "timeout",
            "timed out",
            "name or service not known",
            "temporary failure",
            "econnrefused",
            "econnreset",
            "eof",
            "broken pipe",
        )
    )


def _comp_text(comp: Any, name: str) -> str:
    """Extract a text value from an iCalendar component property."""
    value = comp.get(name)
    return str(value) if value is not None else ""


def _comp_dt(comp: Any, name: str) -> str:
    """Extract a datetime value from an iCalendar component property."""
    import datetime

    value = comp.get(name)
    if value is None:
        return ""
    moment = getattr(value, "dt", value)
    # datetime is a subclass of date — both serialise via isoformat().
    if isinstance(moment, datetime.date):
        return moment.isoformat()
    return str(moment)


class CalDavClient:
    """Typed wrapper around ``caldav.DAVClient`` for Radicale.

    All operations convert caldav/requests exceptions to
    :class:`OperationError` with appropriate codes.

    Args:
        url: Radicale server URL.
        username: Radicale username.
        password: Radicale password.

    Raises:
        OperationError: If authentication fails.
    """

    def __init__(
        self, url: str, username: str, password: str, default_calendar: str = ""
    ) -> None:
        # ``caldav`` ships incomplete type information (mypy resolves the
        # module to ``object``), so route it through ``Any`` to keep the
        # wrapper strict-clean without per-call ignores.
        import caldav

        self._caldav: Any = caldav

        self._url = url
        self._default_calendar = default_calendar
        try:
            self._client = self._caldav.DAVClient(
                url=url, username=username, password=password
            )
            self._principal = self._client.principal()
            logger.info("CalDavClient connected to %s as %s", url, username)
        except self._caldav.error.AuthorizationError as exc:
            logger.exception("CalDAV auth failed for %s as %s: %s", url, username, exc)
            raise OperationError(
                code="auth_failed",
                message=f"Authentication failed: {exc}",
            ) from exc
        except Exception as exc:
            logger.exception("Failed to connect to Radicale at %s: %s", url, exc)
            raise OperationError(
                code="caldav_error",
                message=f"Failed to connect to Radicale: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _iso_date_range(start: str, end: str) -> tuple[Any, Any]:
        """Parse ISO 8601 strings into date/datetime objects for caldav."""
        import datetime

        def _parse(s: str) -> Any:
            s = s.strip()
            try:
                return datetime.datetime.fromisoformat(s)
            except (ValueError, TypeError):
                pass
            try:
                return datetime.date.fromisoformat(s)
            except (ValueError, TypeError):
                return s

        return _parse(start), _parse(end)

    @staticmethod
    def _to_calendar_event(obj: Any, calendar_id: str = "") -> CalendarEvent:
        """Convert a caldav event object to our :class:`CalendarEvent`.

        Reads via caldav 2.0's ``icalendar_component`` (the ``icalendar`` lib),
        replacing the deprecated ``vobject_instance``.
        """
        comp = obj.icalendar_component

        return CalendarEvent(
            uid=_comp_text(comp, "UID"),
            summary=_comp_text(comp, "SUMMARY"),
            description=_comp_text(comp, "DESCRIPTION"),
            location=_comp_text(comp, "LOCATION"),
            dtstart=_comp_dt(comp, "DTSTART"),
            dtend=_comp_dt(comp, "DTEND"),
            calendar_id=calendar_id,
        )

    @staticmethod
    def _to_task(obj: Any, calendar_id: str = "") -> Task:
        """Convert a caldav VTODO object to our :class:`Task`.

        Reads via caldav 2.0's ``icalendar_component`` (the ``icalendar`` lib),
        same pattern as ``_to_calendar_event`` but for VTODO fields.
        """
        comp = obj.icalendar_component

        return Task(
            uid=_comp_text(comp, "UID"),
            summary=_comp_text(comp, "SUMMARY"),
            description=_comp_text(comp, "DESCRIPTION"),
            dtstart=_comp_dt(comp, "DTSTART"),
            due=_comp_dt(comp, "DUE"),
            status=_comp_text(comp, "STATUS"),
            calendar_id=calendar_id,
        )

    @staticmethod
    def _to_contact(obj: Any, addressbook_id: str = "") -> Contact:
        """Convert a caldav vCard object to our :class:`Contact`.

        ``icalendar`` parses iCalendar only (not vCard), so this reads the raw
        vCard text (``obj.data``) directly instead of the deprecated
        ``vobject_instance``.
        """
        fields: dict[str, str] = {}
        for line in (obj.data or "").splitlines():
            name, sep, value = line.partition(":")
            if not sep:
                continue
            # Property name without parameters (e.g. "TEL;TYPE=cell" -> "TEL").
            key = name.split(";", 1)[0].strip().upper()
            fields.setdefault(key, value)  # first occurrence wins

        address = ""
        adr = fields.get("ADR", "")
        if adr:
            # vCard ADR is structured (PO;ext;street;city;region;postal;country).
            # Split on ";" separators while respecting backslash-escaping:
            #   \\ → literal backslash (does NOT escape the following char)
            #   \; → escaped semicolon (literal ";", not a separator)
            #   \n → newline
            #   \, → literal comma
            components: list[str] = []
            current: list[str] = []
            i = 0
            while i < len(adr):
                ch = adr[i]
                if ch == "\\" and i + 1 < len(adr):
                    nxt = adr[i + 1]
                    if nxt == "\\":
                        current.append("\\")
                        i += 2
                        continue
                    elif nxt == ";":
                        current.append(";")
                        i += 2
                        continue
                    elif nxt == ",":
                        current.append(",")
                        i += 2
                        continue
                    elif nxt == "n":
                        current.append("\n")
                        i += 2
                        continue
                    else:
                        # Unknown escape — keep both chars.
                        current.append(ch)
                        current.append(nxt)
                        i += 2
                        continue
                elif ch == ";":
                    components.append("".join(current))
                    current = []
                    i += 1
                else:
                    current.append(ch)
                    i += 1
            components.append("".join(current))
            address = ", ".join(c for c in components if c)

        return Contact(
            uid=CalDavClient._unescape_text(fields.get("UID", "")),
            full_name=CalDavClient._unescape_text(fields.get("FN", "")),
            email=CalDavClient._unescape_text(fields.get("EMAIL", "")),
            phone=CalDavClient._unescape_text(fields.get("TEL", "")),
            address=address,
            addressbook_id=addressbook_id,
        )

    def _get_calendar(self, calendar_id: str = "") -> Any:
        """Return a caldav calendar object by name, or the default.

        When *calendar_id* is empty, resolve in order:
        1. ``self._default_calendar`` by name (when configured).
        2. The first calendar (``calendars[0]``) as a last-resort fallback.
        """
        calendars = self._principal.calendars()
        if not calendars:
            raise OperationError(
                code="not_found",
                message="No calendars found on the server.",
            )
        if calendar_id:
            for cal in calendars:
                if cal.name == calendar_id:
                    return cal
            raise OperationError(
                code="not_found",
                message=f"Calendar {calendar_id!r} not found.",
            )
        # Resolve the configured default calendar by name.
        if self._default_calendar:
            for cal in calendars:
                if cal.name == self._default_calendar:
                    return cal
            raise OperationError(
                code="not_found",
                message=(f"Default calendar {self._default_calendar!r} not found."),
            )
        # Last-resort fallback: first calendar (preserves legacy behavior).
        return calendars[0]

    def _iter_calendars(self, calendar_id: str = "") -> list[Any]:
        """Return calendars to iterate over.

        When *calendar_id* is non-empty, returns a single-element list
        containing the named calendar.  When empty, returns **all**
        calendars (raising ``not_found`` if none exist).
        """
        if calendar_id:
            return [self._get_calendar(calendar_id)]
        calendars = self._principal.calendars()
        if not calendars:
            raise OperationError(
                code="not_found",
                message="No calendars found on the server.",
            )
        return cast(list[Any], calendars)

    def _get_addressbook(self, addressbook_id: str = "") -> Any:
        """Return a caldav addressbook object by name, or the default."""
        addressbooks = self._principal.addressbooks()
        if not addressbooks:
            raise OperationError(
                code="not_found",
                message="No address books found on the server.",
            )
        if addressbook_id:
            for ab in addressbooks:
                if ab.name == addressbook_id:
                    return ab
            raise OperationError(
                code="not_found",
                message=f"Address book {addressbook_id!r} not found.",
            )
        return addressbooks[0]

    @staticmethod
    def _escape_text(value: str) -> str:
        r"""Escape special characters for iCalendar/vCard text values.

        Per RFC 5545 §3.3.11 and RFC 6350 §3.4, the following characters
        must be escaped with a backslash in text property values:
        ``\`` → ``\\``, ``;`` → ``\;``, ``,`` → ``\,``, newline → ``\n``.
        """
        if not value:
            return value
        result = value.replace("\\", "\\\\")
        result = result.replace(";", "\\;")
        result = result.replace(",", "\\,")
        result = result.replace("\n", "\\n")
        return result

    @staticmethod
    def _unescape_text(value: str) -> str:
        """Reverse the escaping applied by :meth:`_escape_text`.

        Uses a placeholder for ``\\\\`` to avoid creating spurious
        escape sequences during sequential replacement.  Restores
        ``\\n`` → ``\n``, ``\\;`` → ``;``, ``\\,`` → ``,``,
        ``\\\\`` → ``\\``.
        """
        if not value:
            return value
        # Replace \\ with a sentinel to avoid it forming spurious
        # \; or \, sequences in later steps.
        SENTINEL = "\x00"
        result = value.replace("\\\\", SENTINEL)
        result = result.replace("\\n", "\n")
        result = result.replace("\\;", ";")
        result = result.replace("\\,", ",")
        result = result.replace(SENTINEL, "\\")
        return result

    @staticmethod
    def _ical_dt(name: str, value: str) -> str:
        """Format a date/datetime as an RFC 5545 iCalendar property line.

        Accepts ISO-8601 (extended ``2026-06-25T15:00:00`` or basic
        ``20260625T150000``) and emits valid iCalendar basic format:
        ``DTSTART:20260625T150000`` (floating), ``...Z`` (UTC), or
        ``DTSTART;VALUE=DATE:20260625`` (date-only). Radicale rejects the
        extended ISO form (colons/dashes) with ``400 Bad Request``.
        """
        import datetime

        s = (value or "").strip()
        if "T" in s:
            try:
                dt = datetime.datetime.fromisoformat(s)
            except (ValueError, TypeError):
                dt = None
            if dt is not None:
                if dt.tzinfo is not None:
                    dt = dt.astimezone(datetime.UTC)
                    return f"{name}:{dt.strftime('%Y%m%dT%H%M%SZ')}"
                return f"{name}:{dt.strftime('%Y%m%dT%H%M%S')}"
        else:
            try:
                d = datetime.date.fromisoformat(s)
                return f"{name};VALUE=DATE:{d.strftime('%Y%m%d')}"
            except (ValueError, TypeError):
                pass
        # Unparseable — pass through (server will reject if truly invalid).
        return f"{name}:{s}"

    def _event_to_ical(self, event: CalendarEvent) -> str:
        """Build an iCalendar string from a :class:`CalendarEvent`."""
        import datetime

        e = self._escape_text
        dtstamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        return (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//robotsix-calendar-agent//EN\n"
            "BEGIN:VEVENT\n"
            f"UID:{event.uid or ''}\n"
            f"DTSTAMP:{dtstamp}\n"
            f"SUMMARY:{e(event.summary)}\n"
            f"DESCRIPTION:{e(event.description)}\n"
            f"LOCATION:{e(event.location)}\n"
            f"{self._ical_dt('DTSTART', event.dtstart)}\n"
            f"{self._ical_dt('DTEND', event.dtend)}\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

    def _contact_to_vcard(self, contact: Contact) -> str:
        """Build a vCard string from a :class:`Contact`."""
        e = self._escape_text
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{contact.uid or ''}",
            f"FN:{e(contact.full_name)}",
        ]
        if contact.email:
            lines.append(f"EMAIL:{e(contact.email)}")
        if contact.phone:
            lines.append(f"TEL:{e(contact.phone)}")
        if contact.address:
            lines.append(f"ADR:;;{e(contact.address)};;;")
        lines.append("END:VCARD")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _wrap_caldav_op(op_name: str) -> Callable[[_F], _F]:
        """Wrap a method with retry logic and standard CalDAV error handling.

        Transient network errors (connection refused, timeout, DNS
        failures) are retried up to 3 times with exponential backoff
        before being converted to an ``OperationError``.

        ``OperationError`` exceptions are re-raised as-is.
        All other exceptions are logged and wrapped in an
        ``OperationError`` with code ``"caldav_error"``.
        """

        def decorator(func: _F) -> _F:
            retrying_func = tenacity.retry(
                stop=stop_after_attempt(4),  # initial + 3 retries
                wait=wait_exponential(multiplier=1, min=1, max=30),
                retry=(
                    retry_if_exception_type(ConnectionError)
                    | retry_if_exception_type(TimeoutError)
                    | retry_if_exception(_is_transient_exception)
                ),
                reraise=True,
            )(func)

            @functools.wraps(func)
            def wrapper(self: CalDavClient, *args: Any, **kwargs: Any) -> Any:
                try:
                    return retrying_func(self, *args, **kwargs)
                except OperationError:
                    raise
                except self._caldav.lib.error.NotFoundError as exc:
                    raise OperationError(
                        code="not_found",
                        message=f"{op_name}: {exc}",
                    ) from exc
                except self._caldav.lib.error.RateLimitError as exc:
                    raise OperationError(
                        code="rate_limited",
                        message=f"{op_name}: {exc}",
                    ) from exc
                except self._caldav.lib.error.EtagMismatchError as exc:
                    raise OperationError(
                        code="conflict",
                        message=f"{op_name}: {exc}",
                    ) from exc
                except self._caldav.lib.error.AuthorizationError as exc:
                    raise OperationError(
                        code="auth_failed",
                        message=f"{op_name}: {exc}",
                    ) from exc
                except Exception as exc:
                    logger.exception("%s failed: %s", func.__name__, exc)
                    raise OperationError(
                        code="caldav_error",
                        message=f"Failed to {op_name}: {exc}",
                    ) from exc

            return cast(_F, wrapper)

        return decorator

    # ------------------------------------------------------------------
    # Calendar operations (CalDAV)
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list calendars")
    def list_calendars(self) -> list[str]:
        """Return the names of all available calendar collections.

        Only VEVENT / calendar collections are included (addressbooks
        come from the separate ``self._principal.addressbooks()`` and
        are inherently excluded).
        """
        return [cal.name for cal in self._principal.calendars()]

    @_wrap_caldav_op("list events")
    def list_events(
        self, start: str, end: str, calendar_id: str = ""
    ) -> list[CalendarEvent]:
        """Return events in the ISO 8601 date range.

        When *calendar_id* is empty, events are aggregated from **all**
        calendars.  Each event is tagged with its source ``calendar_id``.
        """
        logger.debug(
            "list_events start=%r end=%r calendar_id=%r",
            start,
            end,
            calendar_id,
        )
        start_dt, end_dt = self._iso_date_range(start, end)
        aggregated: list[CalendarEvent] = []
        for cal in self._iter_calendars(calendar_id):
            results = cal.search(
                start=start_dt,
                end=end_dt,
                event=True,
                expand=False,
            )
            aggregated.extend(
                self._to_calendar_event(r, calendar_id=cal.name) for r in results
            )
        return aggregated

    @_wrap_caldav_op("list tasks")
    def list_tasks(self, calendar_id: str = "") -> list[Task]:
        """Return all VTODO tasks from CalDAV calendar collections.

        When *calendar_id* is empty, tasks are aggregated from **all**
        calendars.  Each task is tagged with its source ``calendar_id``.
        """
        logger.debug("list_tasks calendar_id=%r", calendar_id)
        aggregated: list[Task] = []
        for cal in self._iter_calendars(calendar_id):
            results = cal.search(todo=True)
            aggregated.extend(self._to_task(r, calendar_id=cal.name) for r in results)
        return aggregated

    @_wrap_caldav_op("create event")
    def create_event(
        self, event: CalendarEvent, calendar_id: str = ""
    ) -> CalendarEvent:
        """Create an event; return the event with its server-assigned uid.

        If *calendar_id* is empty, use the default calendar.
        """
        logger.debug(
            "create_event uid=%r calendar_id=%r summary=%r",
            event.uid,
            calendar_id,
            event.summary,
        )
        import uuid

        if not event.uid:
            # Generate a temporary UID; the server may replace it.
            event = CalendarEvent(
                uid=str(uuid.uuid4()),
                summary=event.summary,
                description=event.description,
                location=event.location,
                dtstart=event.dtstart,
                dtend=event.dtend,
                calendar_id=event.calendar_id,
            )
        cal = self._get_calendar(calendar_id)
        ical = self._event_to_ical(event)
        saved = cal.save_event(ical)
        return self._to_calendar_event(saved, calendar_id=cal.name)

    def _find_event_by_uid(self, uid: str) -> tuple[Any, Any] | None:
        """Locate an event by UID across all calendars.

        Returns ``(calendar, event_obj)`` or ``None`` if not found.
        """
        for cal in self._iter_calendars(""):
            event_obj = cal.event(uid=uid)
            if event_obj is not None:
                return cal, event_obj
        return None

    @_wrap_caldav_op("update event")
    def update_event(
        self, uid: str, event: CalendarEvent, calendar_id: str = ""
    ) -> CalendarEvent:
        """Update the event identified by *uid*; return the updated event.

        When *calendar_id* is empty, iterates **all** calendars to locate
        the UID (the UID may live in a non-default collection).  When
        *calendar_id* is given, only that single calendar is searched.

        Raises:
            OperationError: If the UID doesn't exist (code ``"not_found"``).
        """
        logger.debug(
            "update_event uid=%r calendar_id=%r summary=%r",
            uid,
            calendar_id,
            event.summary,
        )
        if calendar_id:
            cal = self._get_calendar(calendar_id)
            existing = cal.event(uid=uid)
            if existing is None:
                raise OperationError(
                    code="not_found",
                    message=f"Event with UID {uid!r} not found.",
                )
        else:
            result = self._find_event_by_uid(uid)
            if result is None:
                raise OperationError(
                    code="not_found",
                    message=f"Event with UID {uid!r} not found.",
                )
            cal, _ = result
        # Build updated iCal with the same UID
        updated = CalendarEvent(
            uid=uid,
            summary=event.summary,
            description=event.description,
            location=event.location,
            dtstart=event.dtstart,
            dtend=event.dtend,
            calendar_id=calendar_id or cal.name,
        )
        ical = self._event_to_ical(updated)
        saved = cal.save_event(ical)
        return self._to_calendar_event(saved, calendar_id=cal.name)

    @_wrap_caldav_op("delete event")
    def delete_event(self, uid: str, calendar_id: str = "") -> None:
        """Delete the event identified by *uid*. Idempotent.

        When *calendar_id* is empty, iterates **all** calendars to locate
        the UID.  Returns ``None`` when the UID does not exist in any
        calendar (already deleted).
        """
        logger.debug("delete_event uid=%r calendar_id=%r", uid, calendar_id)
        if calendar_id:
            cal = self._get_calendar(calendar_id)
            event_obj = cal.event(uid=uid)
            if event_obj is None:
                return None
            event_obj.delete()
        else:
            result = self._find_event_by_uid(uid)
            if result is None:
                return None
            _cal, event_obj = result
            event_obj.delete()
            return None

    # ------------------------------------------------------------------
    # Contacts operations (CardDAV)
    # ------------------------------------------------------------------

    @_wrap_caldav_op("list contacts")
    def list_contacts(self, addressbook_id: str = "") -> list[Contact]:
        """Return all contacts.

        If *addressbook_id* is empty, use the default address book.
        """
        logger.debug("list_contacts addressbook_id=%r", addressbook_id)
        ab = self._get_addressbook(addressbook_id)
        results = ab.search()
        return [self._to_contact(r, addressbook_id=ab.name) for r in results]

    @_wrap_caldav_op("create contact")
    def create_contact(self, contact: Contact, addressbook_id: str = "") -> Contact:
        """Create a contact; return the contact with server-assigned uid."""
        logger.debug(
            "create_contact uid=%r addressbook_id=%r full_name=%r",
            contact.uid,
            addressbook_id,
            contact.full_name,
        )
        import uuid

        if not contact.uid:
            contact = Contact(
                uid=str(uuid.uuid4()),
                full_name=contact.full_name,
                email=contact.email,
                phone=contact.phone,
                address=contact.address,
                addressbook_id=contact.addressbook_id,
            )
        ab = self._get_addressbook(addressbook_id)
        vcard = self._contact_to_vcard(contact)
        saved = ab.save_object(vcard)
        return self._to_contact(saved, addressbook_id=ab.name)

    @_wrap_caldav_op("update contact")
    def update_contact(
        self, uid: str, contact: Contact, addressbook_id: str = ""
    ) -> Contact:
        """Update the contact identified by *uid*; return the updated contact.

        Raises:
            OperationError: If the UID doesn't exist (code ``"not_found"``).
        """
        logger.debug(
            "update_contact uid=%r addressbook_id=%r full_name=%r",
            uid,
            addressbook_id,
            contact.full_name,
        )
        ab = self._get_addressbook(addressbook_id)
        # Fetch to confirm existence — caldav addressbook search by UID
        existing = ab.search(f"UID:{uid}")
        if not existing:
            raise OperationError(
                code="not_found",
                message=f"Contact with UID {uid!r} not found.",
            )
        # Delete the old vcard and create a new one
        existing[0].delete()
        updated = Contact(
            uid=uid,
            full_name=contact.full_name,
            email=contact.email,
            phone=contact.phone,
            address=contact.address,
            addressbook_id=addressbook_id,
        )
        vcard = self._contact_to_vcard(updated)
        saved = ab.save_object(vcard)
        return self._to_contact(saved, addressbook_id=ab.name)

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Perform a one-shot CalDAV reachability check.

        Returns:
            ``{"connected": True, "calendar_count": int}`` on success, or
            ``{"connected": False, "error": str}`` when the probe fails.

        This is called on-demand by ``monitor`` — it does **not** cache
        stale state.
        """
        try:
            calendars = self._principal.calendars()
        except Exception as exc:
            logger.warning("CalDAV health probe failed: %s", exc)
            return {"connected": False, "error": str(exc)}
        else:
            return {"connected": True, "calendar_count": len(calendars)}

    @_wrap_caldav_op("delete contact")
    def delete_contact(self, uid: str, addressbook_id: str = "") -> None:
        """Delete the contact identified by *uid*. Idempotent.

        Returns ``None`` when the UID does not exist (already deleted).
        """
        logger.debug("delete_contact uid=%r addressbook_id=%r", uid, addressbook_id)
        ab = self._get_addressbook(addressbook_id)
        existing = ab.search(f"UID:{uid}")
        if not existing:
            return None
        existing[0].delete()
