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

    def test_raises_not_found_for_unknown_uid(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.return_value = []

        with pytest.raises(OperationError, match="not found"):
            client.delete_contact("unknown")


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
