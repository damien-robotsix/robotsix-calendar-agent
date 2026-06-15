"""CalDAV/CardDAV client wrapper for Radicale.

Typed, self-contained module wrapping the ``caldav`` library.
All caldav-specific exceptions are converted to :class:`OperationError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

__all__ = [
    "CalDavClient",
    "CalendarEvent",
    "Contact",
    "OperationError",
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

    def __init__(self, url: str, username: str, password: str) -> None:
        import caldav as _caldav  # type: ignore[import-not-found]

        self._url = url
        try:
            self._client = _caldav.DAVClient(
                url=url, username=username, password=password
            )
            self._principal = self._client.principal()
        except _caldav.error.AuthorizationError as exc:
            raise OperationError(
                code="auth_failed",
                message=f"Authentication failed: {exc}",
            ) from exc
        except Exception as exc:
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
            # Try datetime first, then date
            for fmt in (
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d",
            ):
                try:
                    return datetime.datetime.strptime(s, fmt)
                except ValueError:
                    continue
            # If no format matches, return the string as-is (caldav may handle it)
            return s

        return _parse(start), _parse(end)

    @staticmethod
    def _to_calendar_event(obj: Any, calendar_id: str = "") -> CalendarEvent:
        """Convert a caldav event object to our :class:`CalendarEvent`."""
        import datetime

        vevent = obj.vobject_instance.vevent
        uid_val: str = getattr(vevent.uid, "value", "")
        summary_val: str = getattr(vevent.summary, "value", "")
        description_val: str = getattr(vevent.description, "value", "")
        location_val: str = getattr(vevent.location, "value", "")

        def _fmt_dt(dt: Any) -> str:
            if isinstance(dt, datetime.datetime):
                return dt.isoformat()
            if isinstance(dt, datetime.date):
                return dt.isoformat()
            return str(dt)

        return CalendarEvent(
            uid=uid_val,
            summary=summary_val,
            description=description_val,
            location=location_val,
            dtstart=_fmt_dt(getattr(vevent.dtstart, "value", "")),
            dtend=_fmt_dt(getattr(vevent.dtend, "value", "")),
            calendar_id=calendar_id,
        )

    @staticmethod
    def _to_contact(obj: Any, addressbook_id: str = "") -> Contact:
        """Convert a caldav vcard object to our :class:`Contact`."""
        vcard = obj.vobject_instance
        uid_raw: Any = getattr(vcard, "uid", None)
        uid_val: str = uid_raw.value if uid_raw else ""
        fn_raw: Any = getattr(vcard, "fn", None)
        fn_val: str = fn_raw.value if fn_raw else ""
        email_val: str = ""
        if hasattr(vcard, "email"):
            email_val = str(vcard.email.value) if vcard.email.value else ""
        phone_val: str = ""
        if hasattr(vcard, "tel"):
            phone_val = str(vcard.tel.value) if vcard.tel.value else ""
        address_val: str = ""
        if hasattr(vcard, "adr"):
            address_val = str(vcard.adr.value) if vcard.adr.value else ""

        return Contact(
            uid=uid_val,
            full_name=fn_val,
            email=email_val,
            phone=phone_val,
            address=address_val,
            addressbook_id=addressbook_id,
        )

    def _get_calendar(self, calendar_id: str = "") -> Any:
        """Return a caldav calendar object by name, or the default."""
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
        return calendars[0]

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

    def _event_to_ical(self, event: CalendarEvent) -> str:
        """Build an iCalendar string from a :class:`CalendarEvent`."""
        return (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//robotsix-calendar-agent//EN\n"
            "BEGIN:VEVENT\n"
            f"UID:{event.uid or ''}\n"
            f"SUMMARY:{event.summary}\n"
            f"DESCRIPTION:{event.description}\n"
            f"LOCATION:{event.location}\n"
            f"DTSTART:{event.dtstart}\n"
            f"DTEND:{event.dtend}\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )

    def _contact_to_vcard(self, contact: Contact) -> str:
        """Build a vCard string from a :class:`Contact`."""
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{contact.uid or ''}",
            f"FN:{contact.full_name}",
        ]
        if contact.email:
            lines.append(f"EMAIL:{contact.email}")
        if contact.phone:
            lines.append(f"TEL:{contact.phone}")
        if contact.address:
            lines.append(f"ADR:;;{contact.address};;;")
        lines.append("END:VCARD")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Calendar operations (CalDAV)
    # ------------------------------------------------------------------

    def list_events(
        self, start: str, end: str, calendar_id: str = ""
    ) -> list[CalendarEvent]:
        """Return events in the ISO 8601 date range.

        If *calendar_id* is empty, search all calendars.
        """
        try:
            start_dt, end_dt = self._iso_date_range(start, end)
            cal = self._get_calendar(calendar_id)
            results = cal.search(
                start=start_dt,
                end=end_dt,
                event=True,
                expand=False,
            )
            return [self._to_calendar_event(r, calendar_id=cal.name) for r in results]
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to list events: {exc}",
            ) from exc

    def create_event(
        self, event: CalendarEvent, calendar_id: str = ""
    ) -> CalendarEvent:
        """Create an event; return the event with its server-assigned uid.

        If *calendar_id* is empty, use the default calendar.
        """
        try:
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
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to create event: {exc}",
            ) from exc

    def update_event(
        self, uid: str, event: CalendarEvent, calendar_id: str = ""
    ) -> CalendarEvent:
        """Update the event identified by *uid*; return the updated event.

        Raises:
            OperationError: If the UID doesn't exist (code ``"not_found"``).
        """
        try:
            cal = self._get_calendar(calendar_id)
            # Fetch the existing event to confirm it exists
            existing = cal.event(uid=uid)
            if existing is None:
                raise OperationError(
                    code="not_found",
                    message=f"Event with UID {uid!r} not found.",
                )
            # Build updated iCal with the same UID
            updated = CalendarEvent(
                uid=uid,
                summary=event.summary,
                description=event.description,
                location=event.location,
                dtstart=event.dtstart,
                dtend=event.dtend,
                calendar_id=calendar_id,
            )
            ical = self._event_to_ical(updated)
            saved = cal.save_event(ical)
            return self._to_calendar_event(saved, calendar_id=cal.name)
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to update event: {exc}",
            ) from exc

    def delete_event(self, uid: str, calendar_id: str = "") -> None:
        """Delete the event identified by *uid*. Idempotent on already-deleted.

        Raises:
            OperationError: If the event is not found (code ``"not_found"``).
        """
        try:
            cal = self._get_calendar(calendar_id)
            event_obj = cal.event(uid=uid)
            if event_obj is None:
                raise OperationError(
                    code="not_found",
                    message=f"Event with UID {uid!r} not found.",
                )
            event_obj.delete()
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to delete event: {exc}",
            ) from exc

    # ------------------------------------------------------------------
    # Contacts operations (CardDAV)
    # ------------------------------------------------------------------

    def list_contacts(self, addressbook_id: str = "") -> list[Contact]:
        """Return all contacts.

        If *addressbook_id* is empty, search all address books.
        """
        try:
            ab = self._get_addressbook(addressbook_id)
            results = ab.search()
            return [self._to_contact(r, addressbook_id=ab.name) for r in results]
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to list contacts: {exc}",
            ) from exc

    def create_contact(self, contact: Contact, addressbook_id: str = "") -> Contact:
        """Create a contact; return the contact with server-assigned uid."""
        try:
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
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to create contact: {exc}",
            ) from exc

    def update_contact(
        self, uid: str, contact: Contact, addressbook_id: str = ""
    ) -> Contact:
        """Update the contact identified by *uid*; return the updated contact.

        Raises:
            OperationError: If the UID doesn't exist (code ``"not_found"``).
        """
        try:
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
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to update contact: {exc}",
            ) from exc

    def delete_contact(self, uid: str, addressbook_id: str = "") -> None:
        """Delete the contact identified by *uid*. Idempotent.

        Raises:
            OperationError: If the contact is not found (code ``"not_found"``).
        """
        try:
            ab = self._get_addressbook(addressbook_id)
            existing = ab.search(f"UID:{uid}")
            if not existing:
                raise OperationError(
                    code="not_found",
                    message=f"Contact with UID {uid!r} not found.",
                )
            existing[0].delete()
        except OperationError:
            raise
        except Exception as exc:
            raise OperationError(
                code="caldav_error",
                message=f"Failed to delete contact: {exc}",
            ) from exc
