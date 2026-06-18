"""Tests for CalDavClient — all caldav calls mocked."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# Ensure caldav is mockable before any imports
_mock_caldav = MagicMock()
_mock_caldav.error.AuthorizationError = type("AuthorizationError", (Exception,), {})
sys.modules["caldav"] = _mock_caldav

from robotsix_calendar_agent.caldav_client import (  # noqa: E402
    CalDavClient,
    CalendarEvent,
    Contact,
    OperationError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_mock_caldav() -> MagicMock:
    """Reset the mock caldav module between tests."""
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

    return _mock_caldav


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
    return CalendarEvent(**defaults)  # type: ignore[arg-type]


def _mock_vevent(**overrides: str) -> MagicMock:
    """Build a mock vobject-style event."""
    vevent = MagicMock()
    vevent.uid.value = overrides.get("uid", "evt-1")
    vevent.summary.value = overrides.get("summary", "Test Event")
    vevent.description.value = overrides.get("description", "")
    vevent.location.value = overrides.get("location", "")
    vevent.dtstart.value = overrides.get("dtstart", "20260615T090000")
    vevent.dtend.value = overrides.get("dtend", "20260615T100000")
    obj = MagicMock()
    obj.vobject_instance.vevent = vevent
    return obj


def _mock_vcard(**overrides: str) -> MagicMock:
    """Build a mock vobject-style vcard."""
    vcard = MagicMock()
    vcard.uid = MagicMock()
    vcard.uid.value = overrides.get("uid", "cnt-1")
    vcard.fn = MagicMock()
    vcard.fn.value = overrides.get("full_name", "John Doe")
    vcard.email = MagicMock()
    vcard.email.value = overrides.get("email", "")
    vcard.tel = MagicMock()
    vcard.tel.value = overrides.get("phone", "")
    vcard.adr = MagicMock()
    vcard.adr.value = overrides.get("address", "")
    obj = MagicMock()
    obj.vobject_instance = vcard
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

    def test_raises_not_found_for_unknown_uid(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.return_value = None

        with pytest.raises(OperationError, match="not found"):
            client.delete_event("unknown")


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

        obj = MagicMock()
        ve = obj.vobject_instance.vevent
        ve.uid.value = "evt-x"
        ve.summary.value = "Sum"
        ve.description.value = "Desc"
        ve.location.value = "Loc"
        ve.dtstart.value = datetime.datetime(2026, 6, 15, 9, 0, 0)
        ve.dtend.value = datetime.date(2026, 6, 15)

        event = CalDavClient._to_calendar_event(obj, calendar_id="cal")

        assert event.dtstart == "2026-06-15T09:00:00"
        assert event.dtend == "2026-06-15"
        assert event.calendar_id == "cal"


class TestToContact:
    def test_missing_optional_fields_yield_empty(self) -> None:
        vcard = MagicMock(spec=["uid", "fn"])
        vcard.uid = MagicMock()
        vcard.uid.value = "cnt-9"
        vcard.fn = MagicMock()
        vcard.fn.value = "Only Name"
        obj = MagicMock()
        obj.vobject_instance = vcard

        contact = CalDavClient._to_contact(obj, addressbook_id="ab")

        assert contact.uid == "cnt-9"
        assert contact.full_name == "Only Name"
        assert contact.email == ""
        assert contact.phone == ""
        assert contact.address == ""

    def test_empty_optional_values_yield_empty(self) -> None:
        vcard = MagicMock()
        vcard.uid.value = "cnt-10"
        vcard.fn.value = "Name"
        vcard.email.value = ""
        vcard.tel.value = ""
        vcard.adr.value = ""
        obj = MagicMock()
        obj.vobject_instance = vcard

        contact = CalDavClient._to_contact(obj)

        assert contact.email == ""
        assert contact.phone == ""
        assert contact.address == ""

    def test_no_uid_or_fn_yield_empty(self) -> None:
        vcard = MagicMock(spec=[])
        obj = MagicMock()
        obj.vobject_instance = vcard

        contact = CalDavClient._to_contact(obj)

        assert contact.uid == ""
        assert contact.full_name == ""


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
