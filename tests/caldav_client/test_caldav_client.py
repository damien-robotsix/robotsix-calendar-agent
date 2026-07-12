"""Integration tests for CalDavClient — cross-mixin operations and error propagation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from robotsix_calendar_agent.caldav_client import (
    CalDavClient,
    CalendarEvent,
    Contact,
)
from robotsix_calendar_agent.caldav_client.exceptions import (
    CalDAVError,
    NotFoundError,
)

# ---------------------------------------------------------------------------
# Helpers (local copies needed by these tests)
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
# Across-calendar operations
# ---------------------------------------------------------------------------


class TestUpdateEventAcrossCalendars:
    def test_locate_uid_across_all_calendars(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.event.return_value = None  # not here
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.event.return_value = _mock_vevent(uid="evt-1", summary="Old")
        cal_b.save_event.return_value = _mock_vevent(uid="evt-1", summary="Updated")
        client._principal.calendars.return_value = [cal_a, cal_b]

        event = _make_event(summary="Updated")
        result = client.update_event("evt-1", event)

        assert result.summary == "Updated"
        cal_a.event.assert_called_once_with(uid="evt-1")
        cal_b.event.assert_called_once_with(uid="evt-1")

    def test_raises_when_uid_not_found_anywhere(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.event.return_value = None
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.event.return_value = None
        client._principal.calendars.return_value = [cal_a, cal_b]

        with pytest.raises(NotFoundError, match="not found"):
            client.update_event("unknown", _make_event())

    def test_explicit_calendar_id_still_works(self, client: CalDavClient) -> None:
        cal = MagicMock(name="Damien")
        cal.name = "Damien"
        cal.event.return_value = _mock_vevent(uid="evt-1", summary="Old")
        cal.save_event.return_value = _mock_vevent(uid="evt-1", summary="Updated")
        client._principal.calendars.return_value = [cal]

        event = _make_event(summary="Updated")
        result = client.update_event("evt-1", event, calendar_id="Damien")

        assert result.summary == "Updated"
        assert cal.save_event.called


class TestDeleteEventAcrossCalendars:
    def test_locate_and_delete_across_calendars(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.event.return_value = None
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        mock_evt = MagicMock()
        cal_b.event.return_value = mock_evt
        client._principal.calendars.return_value = [cal_a, cal_b]

        client.delete_event("evt-1")

        mock_evt.delete.assert_called_once()
        cal_a.event.assert_called_once_with(uid="evt-1")
        cal_b.event.assert_called_once_with(uid="evt-1")

    def test_idempotent_when_not_found_anywhere(self, client: CalDavClient) -> None:
        cal_a = MagicMock(name="Robotsix")
        cal_a.name = "Robotsix"
        cal_a.event.return_value = None
        cal_b = MagicMock(name="Birthdays")
        cal_b.name = "Birthdays"
        cal_b.event.return_value = None
        client._principal.calendars.return_value = [cal_a, cal_b]

        result = client.delete_event("unknown")
        assert result is None

    def test_explicit_calendar_id_still_works(self, client: CalDavClient) -> None:
        cal = MagicMock(name="Damien")
        cal.name = "Damien"
        mock_evt = MagicMock()
        cal.event.return_value = mock_evt
        client._principal.calendars.return_value = [cal]

        client.delete_event("evt-1", calendar_id="Damien")

        mock_evt.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Error propagation for each operation
# ---------------------------------------------------------------------------


class TestErrorPropagation:
    def test_list_events_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []
        with pytest.raises(NotFoundError) as exc_info:
            client.list_events("2026-01-01", "2026-01-31")
        assert exc_info.value.code == "not_found"

    def test_list_tasks_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []
        with pytest.raises(NotFoundError) as exc_info:
            client.list_tasks()
        assert exc_info.value.code == "not_found"

    def test_create_event_wraps_exception(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.save_event.side_effect = Exception("boom")
        with pytest.raises(CalDAVError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "caldav_error"

    def test_create_event_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.calendars.return_value = []
        with pytest.raises(NotFoundError) as exc_info:
            client.create_event(_make_event())
        assert exc_info.value.code == "not_found"

    def test_create_contact_reraises_operation_error(
        self, client: CalDavClient
    ) -> None:
        client._principal.addressbooks.return_value = []
        with pytest.raises(NotFoundError) as exc_info:
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
        with pytest.raises(CalDAVError) as exc_info:
            client.update_event("evt-1", _make_event())
        assert exc_info.value.code == "caldav_error"

    def test_delete_event_wraps_exception(self, client: CalDavClient) -> None:
        cal = client._principal.calendars.return_value[0]
        cal.event.side_effect = Exception("boom")
        with pytest.raises(CalDAVError) as exc_info:
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
        with pytest.raises(CalDAVError) as exc_info:
            client.list_contacts()
        assert exc_info.value.code == "caldav_error"

    def test_list_contacts_reraises_operation_error(self, client: CalDavClient) -> None:
        client._principal.addressbooks.return_value = []
        with pytest.raises(NotFoundError) as exc_info:
            client.list_contacts()
        assert exc_info.value.code == "not_found"

    def test_create_contact_wraps_exception(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.save_object.side_effect = Exception("boom")
        with pytest.raises(CalDAVError) as exc_info:
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
        with pytest.raises(CalDAVError) as exc_info:
            client.update_contact("cnt-1", Contact(full_name="X"))
        assert exc_info.value.code == "caldav_error"

    def test_delete_contact_wraps_exception(self, client: CalDavClient) -> None:
        ab = client._principal.addressbooks.return_value[0]
        ab.search.side_effect = Exception("boom")
        with pytest.raises(CalDAVError) as exc_info:
            client.delete_contact("cnt-1")
        assert exc_info.value.code == "caldav_error"
