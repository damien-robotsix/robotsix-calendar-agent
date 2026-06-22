"""Tests for CalDavClient — all caldav calls mocked."""

from __future__ import annotations

import sys
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest

from robotsix_calendar_agent.caldav_client import (
    CalDavClient,
    CalendarEvent,
    Contact,
    OperationError,
)

# Mock object prepared at module level but NOT yet injected into
# sys.modules.  The reset_mock_caldav fixture (autouse) temporarily
# swaps it in for each test so that session-scoped integration
# fixtures (like caldav_client in tests/caldav_test_server.py) can
# import the real caldav library without interference.
_mock_caldav = MagicMock()
_mock_caldav.error.AuthorizationError = type("AuthorizationError", (Exception,), {})

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_mock_caldav() -> Generator[MagicMock, None, None]:
    """Replace caldav in sys.modules with mock, reset between tests.

    Saves and restores the real caldav module so that integration
    tests (which use the same session) can import the real library
    outside of mocked test cases.
    """
    original = sys.modules.get("caldav")
    sys.modules["caldav"] = _mock_caldav
    _mock_caldav.reset_mock(return_value=True, side_effect=True)
    # Re-establish default mock structure
    mock_client = MagicMock()
    mock_principal = MagicMock()
    _mock_caldav.DAVClient.return_value = mock_client
    mock_client.principal.return_value = mock_principal

    mock_cal = MagicMock()
    mock_cal.name = "default-cal"
    mock_principal.calendars.return_value = [mock_cal]

    mock_ab = MagicMock()
    mock_ab.name = "default-ab"
    mock_principal.addressbooks.return_value = [mock_ab]

    yield _mock_caldav

    # Restore the real caldav module (or remove if it wasn't there)
    if original is not None:
        sys.modules["caldav"] = original
    else:
        sys.modules.pop("caldav", None)


@pytest.fixture
def client() -> CalDavClient:
    """Return a CalDavClient with a mocked DAV backend."""
    return CalDavClient("https://example.com", "user", "pass")


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------


def _make_event(**overrides: str) -> CalendarEvent:
    defaults: dict[str, str] = {
        "uid": "",
        "summary": "Test Event",
        "description": "desc",
        "location": "room",
        "dtstart": "2026-06-15T09:00:00",
        "dtend": "2026-06-15T10:00:00",
        "calendar_id": "",
    }
    defaults.update(overrides)
    return CalendarEvent(**defaults)


def _mock_vevent(**overrides: Any) -> MagicMock:
    """Build a mock caldav object exposing ``icalendar_component`` (caldav 2.0)."""
    import datetime

    values: dict[str, Any] = {
        "UID": overrides.get("uid", "evt-1"),
        "SUMMARY": overrides.get("summary", "Test Event"),
        "DESCRIPTION": overrides.get("description", ""),
        "LOCATION": overrides.get("location", ""),
        "DTSTART": MagicMock(
            dt=overrides.get("dtstart", datetime.datetime(2026, 6, 15, 9, 0, 0))
        ),
        "DTEND": MagicMock(
            dt=overrides.get("dtend", datetime.datetime(2026, 6, 15, 10, 0, 0))
        ),
    }
    comp = MagicMock()
    comp.get.side_effect = lambda name, default=None: values.get(name, default)
    obj = MagicMock()
    obj.icalendar_component = comp
    return obj


def _mock_vcard(**overrides: str) -> MagicMock:
    """Build a mock caldav object exposing raw vCard ``data`` (caldav 2.0)."""
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"UID:{overrides.get('uid', 'cnt-1')}",
        f"FN:{overrides.get('full_name', 'John Doe')}",
    ]
    if overrides.get("email"):
        lines.append(f"EMAIL:{overrides['email']}")
    if overrides.get("phone"):
        lines.append(f"TEL:{overrides['phone']}")
    if overrides.get("address"):
        lines.append(f"ADR:;;{overrides['address']};;;")
    lines.append("END:VCARD")
    obj = MagicMock()
    obj.data = "\n".join(lines) + "\n"
    return obj


# ---------------------------------------------------------------------------
# Calendar operations
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_returns_list_of_calendar_events(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.search.return_value = [_mock_vevent(), _mock_vevent(uid="evt-2")]

        result = client.list_events("2026-06-01", "2026-06-30")

        assert len(result) == 2
        assert isinstance(result[0], CalendarEvent)
        assert result[0].uid == "evt-1"
        assert result[1].uid == "evt-2"


class TestCreateEvent:
    def test_returns_event_with_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.return_value = _mock_vevent(uid="new-uid")

        event = _make_event()
        result = client.create_event(event)

        assert isinstance(result, CalendarEvent)
        assert result.uid == "new-uid"
        cal.save_event.assert_called_once()


class TestUpdateEvent:
    def test_returns_updated_event(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = _mock_vevent(uid="evt-1")
        cal.save_event.return_value = _mock_vevent(uid="evt-1", summary="Updated")

        event = _make_event(summary="Updated")
        result = client.update_event("evt-1", event)

        assert result.summary == "Updated"

    def test_raises_not_found_for_unknown_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = None

        with pytest.raises(OperationError, match="not found"):
            client.update_event("unknown", _make_event())


class TestDeleteEvent:
    def test_succeeds(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        mock_event = MagicMock()
        cal.event.return_value = mock_event

        client.delete_event("evt-1")  # should not raise

        mock_event.delete.assert_called_once()

    def test_returns_none_for_unknown_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = None

        result = client.delete_event("unknown")
        assert result is None


# ---------------------------------------------------------------------------
# Contacts operations
# ---------------------------------------------------------------------------


class TestListContacts:
    def test_returns_list_of_contacts(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = [_mock_vcard(), _mock_vcard(uid="cnt-2")]

        result = client.list_contacts()

        assert len(result) == 2
        assert isinstance(result[0], Contact)
        assert result[0].uid == "cnt-1"
        assert result[1].uid == "cnt-2"


class TestCreateContact:
    def test_returns_contact_with_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.save_object.return_value = _mock_vcard(uid="new-cnt")

        contact = Contact(full_name="Jane Doe")
        result = client.create_contact(contact)

        assert isinstance(result, Contact)
        assert result.uid == "new-cnt"
        ab.save_object.assert_called_once()


class TestUpdateContact:
    def test_returns_updated_contact(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = [_mock_vcard(uid="cnt-1")]
        ab.save_object.return_value = _mock_vcard(uid="cnt-1", full_name="Jane Updated")

        contact = Contact(full_name="Jane Updated")
        result = client.update_contact("cnt-1", contact)

        assert result.full_name == "Jane Updated"

    def test_raises_not_found_for_unknown_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = []

        with pytest.raises(OperationError, match="not found"):
            client.update_contact("unknown", Contact(full_name="X"))


class TestDeleteContact:
    def test_succeeds(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        mock_contact = MagicMock()
        ab.search.return_value = [mock_contact]

        client.delete_contact("cnt-1")  # should not raise

        mock_contact.delete.assert_called_once()

    def test_returns_none_for_unknown_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = []

        result = client.delete_contact("unknown")

        assert result is None


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestAuthFailure:
    def test_raises_auth_failed_on_authorization_error(self) -> None:
        _mock_caldav.DAVClient.side_effect = _mock_caldav.error.AuthorizationError(
            "bad creds"
        )

        with pytest.raises(OperationError) as exc_info:
            CalDavClient("https://x.com", "user", "wrong")
        assert exc_info.value.code == "auth_failed"


class TestTransportFailure:
    def test_raises_caldav_error_on_transport_exception(
        self, client: CalDavClient
    ) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.search.side_effect = Exception("connection refused")

        with pytest.raises(OperationError) as exc_info:
            client.list_events("2026-01-01", "2026-01-31")
        assert exc_info.value.code == "caldav_error"

    def test_retries_transient_failures_then_succeeds(
        self, client: CalDavClient
    ) -> None:
        """Verify retry actually kicks in: fail twice, succeed on third attempt."""
        cal = client._principal.calendars.return_value[0]
        cal.search.side_effect = [
            Exception("connection refused"),
            Exception("connection reset"),
            [_mock_vevent(uid="evt-1")],
        ]

        result = client.list_events("2026-01-01", "2026-01-31")

        assert len(result) == 1
        assert result[0].uid == "evt-1"
        assert cal.search.call_count == 3


class TestConnectFailure:
    def test_raises_caldav_error_on_generic_connect_exception(self) -> None:
        _mock_caldav.DAVClient.side_effect = Exception("connection refused")

        with pytest.raises(OperationError) as exc_info:
            CalDavClient("https://x.com", "user", "pass")
        assert exc_info.value.code == "caldav_error"


# ---------------------------------------------------------------------------
# Calendar / addressbook resolution
# ---------------------------------------------------------------------------


class TestGetCalendar:
    def test_no_calendars_raises_not_found(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []

        with pytest.raises(OperationError) as exc_info:
            client._get_calendar()
        assert exc_info.value.code == "not_found"

    def test_named_calendar_returned(self, client: CalDavClient) -> None:
        cal_a = MagicMock()
        cal_a.name = "work"
        cal_b = MagicMock()
        cal_b.name = "home"
        client._principal.calendars.return_value = [cal_a, cal_b]

        assert client._get_calendar("home") is cal_b

    def test_named_calendar_not_found_raises(self, client: CalDavClient) -> None:
        cal_a = MagicMock()
        cal_a.name = "work"
        client._principal.calendars.return_value = [cal_a]

        with pytest.raises(OperationError) as exc_info:
            client._get_calendar("missing")
        assert exc_info.value.code == "not_found"


class TestGetAddressbook:
    def test_no_addressbooks_raises_not_found(self, client: CalDavClient) -> None:
        client._principal.addressbooks.return_value = []

        with pytest.raises(OperationError) as exc_info:
            client._get_addressbook()
        assert exc_info.value.code == "not_found"

    def test_named_addressbook_returned(self, client: CalDavClient) -> None:
        ab_a = MagicMock()
        ab_a.name = "personal"
        ab_b = MagicMock()
        ab_b.name = "team"
        client._principal.addressbooks.return_value = [ab_a, ab_b]

        assert client._get_addressbook("team") is ab_b

    def test_named_addressbook_not_found_raises(self, client: CalDavClient) -> None:
        ab_a = MagicMock()
        ab_a.name = "personal"
        client._principal.addressbooks.return_value = [ab_a]

        with pytest.raises(OperationError) as exc_info:
            client._get_addressbook("missing")
        assert exc_info.value.code == "not_found"


# ---------------------------------------------------------------------------
# Conversion / serialization helpers
# ---------------------------------------------------------------------------


class TestIsoDateRange:
    def test_unparseable_returned_as_string(self) -> None:
        start, end = CalDavClient._iso_date_range("not-a-date", "also-bad")
        assert start == "not-a-date"
        assert end == "also-bad"

    def test_date_only_format(self) -> None:
        import datetime

        start, _ = CalDavClient._iso_date_range("2026-06-15", "2026-06-16")
        assert isinstance(start, datetime.datetime)

    def test_datetime_with_utc_z_suffix(self) -> None:
        import datetime

        start, end = CalDavClient._iso_date_range(
            "2026-03-01T10:00:00Z", "2026-03-01T11:00:00Z"
        )
        assert isinstance(start, datetime.datetime)
        assert isinstance(end, datetime.datetime)
        assert start.tzinfo is not None
        assert end.tzinfo is not None

    def test_datetime_with_timezone_offset(self) -> None:
        import datetime

        start, end = CalDavClient._iso_date_range(
            "2026-01-15T14:30:00+01:00", "2026-01-15T15:30:00+01:00"
        )
        assert isinstance(start, datetime.datetime)
        assert isinstance(end, datetime.datetime)
        assert start.tzinfo is not None
        assert end.tzinfo is not None


class TestToCalendarEvent:
    def test_formats_datetime_and_date_values(self) -> None:
        import datetime

        obj = _mock_vevent(
            uid="evt-x",
            summary="Sum",
            description="Desc",
            location="Loc",
            dtstart=datetime.datetime(2026, 6, 15, 9, 0, 0),
            dtend=datetime.date(2026, 6, 15),
        )

        event = CalDavClient._to_calendar_event(obj, calendar_id="cal")

        assert event.uid == "evt-x"
        assert event.dtstart == "2026-06-15T09:00:00"
        assert event.dtend == "2026-06-15"
        assert event.calendar_id == "cal"

    def test_missing_fields_yield_empty(self) -> None:
        comp = MagicMock()
        comp.get.side_effect = lambda name, default=None: default
        obj = MagicMock()
        obj.icalendar_component = comp

        event = CalDavClient._to_calendar_event(obj)

        assert event.uid == ""
        assert event.summary == ""
        assert event.dtstart == ""
        assert event.dtend == ""


class TestToContact:
    def test_all_fields_parsed_from_vcard(self) -> None:
        obj = _mock_vcard(
            uid="cnt-1",
            full_name="John Doe",
            email="j@example.com",
            phone="555-1234",
            address="123 Main St",
        )

        contact = CalDavClient._to_contact(obj, addressbook_id="ab")

        assert contact.uid == "cnt-1"
        assert contact.full_name == "John Doe"
        assert contact.email == "j@example.com"
        assert contact.phone == "555-1234"
        assert contact.address == "123 Main St"
        assert contact.addressbook_id == "ab"

    def test_missing_optional_fields_yield_empty(self) -> None:
        obj = _mock_vcard(uid="cnt-9", full_name="Only Name")

        contact = CalDavClient._to_contact(obj, addressbook_id="ab")

        assert contact.uid == "cnt-9"
        assert contact.full_name == "Only Name"
        assert contact.email == ""
        assert contact.phone == ""
        assert contact.address == ""

    def test_no_uid_or_fn_yield_empty(self) -> None:
        obj = MagicMock()
        obj.data = "BEGIN:VCARD\nVERSION:3.0\nEND:VCARD\n"

        contact = CalDavClient._to_contact(obj)

        assert contact.uid == ""
        assert contact.full_name == ""


class TestEscapeText:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("", ""),
            ("plain text", "plain text"),
            (r"back\slash", "back\\\\slash"),
            ("semi;colon", "semi\\;colon"),
            ("comma,text", "comma\\,text"),
            ("line\nbreak", "line\\nbreak"),
            # mixed characters
            ("a\\b;c,d\ne", "a\\\\b\\;c\\,d\\ne"),
            # already-escaped sequences are re-escaped
            (r"already\\escaped", "already\\\\\\\\escaped"),
            ("already\\;escaped", "already\\\\\\;escaped"),
        ],
    )
    def test_escape_text(self, client: CalDavClient, value: str, expected: str) -> None:
        assert client._escape_text(value) == expected


class TestIcalSerialization:
    def test_basic_event(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            uid="evt-1",
            summary="Team Meeting",
            description="Discuss Q3 goals",
            location="Room 101",
            dtstart="20260101T090000Z",
            dtend="20260101T100000Z",
        )
        ical = client._event_to_ical(event)
        assert "SUMMARY:Team Meeting" in ical
        assert "DESCRIPTION:Discuss Q3 goals" in ical
        assert "LOCATION:Room 101" in ical

    def test_iso_extended_dates_converted_to_ical_basic(
        self, client: CalDavClient
    ) -> None:
        # auto-mail / the LLM produce ISO-extended datetimes; Radicale rejects
        # the extended form (colons/dashes) with 400 — they must be normalised.
        event = CalendarEvent(
            uid="evt-iso",
            summary="ISO",
            dtstart="2026-06-25T15:00:00",
            dtend="2026-06-25T16:00:00",
        )
        ical = client._event_to_ical(event)
        assert "DTSTART:20260625T150000" in ical
        assert "DTEND:20260625T160000" in ical
        assert "DTSTART:2026-06-25T15:00:00" not in ical
        assert "DTSTAMP:" in ical

    def test_basic_and_utc_dates_preserved(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            uid="evt-utc",
            summary="UTC",
            dtstart="20260101T090000Z",
            dtend="20260101T100000Z",
        )
        ical = client._event_to_ical(event)
        assert "DTSTART:20260101T090000Z" in ical
        assert "DTEND:20260101T100000Z" in ical

    def test_date_only_uses_value_date(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            uid="evt-day",
            summary="All day",
            dtstart="2026-06-25",
            dtend="2026-06-26",
        )
        ical = client._event_to_ical(event)
        assert "DTSTART;VALUE=DATE:20260625" in ical
        assert "DTEND;VALUE=DATE:20260626" in ical

    def test_escapes_special_characters(self, client: CalDavClient) -> None:
        event = CalendarEvent(
            summary="a\\b;c,d\ne",
            description="desc\\with;special,chars\nhere",
            location="Room; A, B\\C\nDownstairs",
            dtstart="20260101T090000Z",
            dtend="20260101T100000Z",
        )
        ical = client._event_to_ical(event)
        assert "SUMMARY:a\\\\b\\;c\\,d\\ne" in ical
        assert "DESCRIPTION:desc\\\\with\\;special\\,chars\\nhere" in ical
        assert "LOCATION:Room\\; A\\, B\\\\C\\nDownstairs" in ical


class TestVcardSerialization:
    def test_includes_optional_fields(self, client: CalDavClient) -> None:
        contact = Contact(
            full_name="Jane",
            email="jane@example.com",
            phone="555-1234",
            address="123 Main St",
        )
        vcard = client._contact_to_vcard(contact)
        assert "EMAIL:jane@example.com" in vcard
        assert "TEL:555-1234" in vcard
        assert "ADR:;;123 Main St;;;" in vcard

    def test_escapes_special_characters(self, client: CalDavClient) -> None:
        contact = Contact(
            full_name="Smith\\, Jane; Jr.\n",
            email="jane+test\\;@example.com",
            phone="555;1234,ext\n9",
            address="123 Main St; Apt 4\\B\nNY, NY",
        )
        vcard = client._contact_to_vcard(contact)
        assert "FN:Smith\\\\\\, Jane\\; Jr.\\n" in vcard
        assert "EMAIL:jane+test\\\\\\;@example.com" in vcard
        assert "TEL:555\\;1234\\,ext\\n9" in vcard
        assert "ADR:;;123 Main St\\; Apt 4\\\\B\\nNY\\, NY;;;" in vcard


# ---------------------------------------------------------------------------
# Error propagation for each operation
# ---------------------------------------------------------------------------


class TestOperationErrorPropagation:
    def test_list_events_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []
        with pytest.raises(OperationError) as exc_info:
            client.list_events("2026-01-01", "2026-01-31")
        assert exc_info.value.code == "not_found"

    def test_create_event_wraps_exception(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "caldav_error"

    def test_create_event_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []
        with pytest.raises(OperationError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "not_found"

    def test_create_contact_reraises_operation_error(
        self, client: CalDavClient
    ) -> None:
        client._principal.addressbooks.return_value = []
        with pytest.raises(OperationError) as exc_info:
            client.create_contact(Contact(full_name="X"))
        assert exc_info.value.code == "not_found"

    def test_create_event_keeps_existing_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.return_value = _mock_vevent(uid="kept")
        result = client.create_event(_make_event(uid="kept"))
        assert result.uid == "kept"

    def test_update_event_wraps_exception(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.update_event("evt-1", _make_event())
        assert exc_info.value.code == "caldav_error"

    def test_delete_event_wraps_exception(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.delete_event("evt-1")
        assert exc_info.value.code == "caldav_error"

    def test_delete_event_idempotent_on_not_found(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = None
        result = client.delete_event("nonexistent-uid")
        assert result is None

    def test_list_contacts_wraps_exception(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.list_contacts()
        assert exc_info.value.code == "caldav_error"

    def test_list_contacts_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.addressbooks.return_value = []
        with pytest.raises(OperationError) as exc_info:
            client.list_contacts()
        assert exc_info.value.code == "not_found"

    def test_create_contact_wraps_exception(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.save_object.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.create_contact(Contact(full_name="X"))
        assert exc_info.value.code == "caldav_error"

    def test_create_contact_keeps_existing_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.save_object.return_value = _mock_vcard(uid="kept")
        result = client.create_contact(Contact(uid="kept", full_name="X"))
        assert result.uid == "kept"

    def test_update_contact_wraps_exception(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.update_contact("cnt-1", Contact(full_name="X"))
        assert exc_info.value.code == "caldav_error"

    def test_delete_contact_wraps_exception(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.side_effect = Exception("boom")
        with pytest.raises(OperationError) as exc_info:
            client.delete_contact("cnt-1")
        assert exc_info.value.code == "caldav_error"
