"""Integration tests against a live in-process Radicale server.

These tests use the session-scoped ``caldav_client`` fixture from
``tests/caldav_test_server.py`` to exercise real CalDAV protocol
interactions: PROPFIND, REPORT, MKCALENDAR, PUT, DELETE, and iCal
parsing.

Marked ``integration`` so they can be skipped in quick dev loops
with ``pytest -m "not integration"``.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Create + search
# ---------------------------------------------------------------------------


def test_create_event_then_search_by_date(caldav_client: Any) -> None:
    """Save an event and retrieve it via date-range search."""
    principal = caldav_client.principal()
    calendars = principal.calendars()
    cal = calendars[0]

    cal.save_event(
        """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-search-1
DTSTART:20260801T090000
DTEND:20260801T100000
SUMMARY:Integration Test Meeting
END:VEVENT
END:VCALENDAR"""
    )

    results = cal.search(
        start=datetime.datetime(2026, 8, 1),
        end=datetime.datetime(2026, 8, 2),
        event=True,
    )

    assert len(results) == 1
    comp = results[0].icalendar_component
    assert str(comp.get("SUMMARY")) == "Integration Test Meeting"
    assert str(comp.get("UID")) == "test-search-1"


# ---------------------------------------------------------------------------
# Create + delete
# ---------------------------------------------------------------------------


def test_create_event_then_delete(caldav_client: Any) -> None:
    """Save an event, delete it, and verify it is gone."""
    principal = caldav_client.principal()
    calendars = principal.calendars()
    cal = calendars[0]

    cal.save_event(
        """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-delete-1
DTSTART:20260915T140000
DTEND:20260915T150000
SUMMARY:To Be Deleted
END:VEVENT
END:VCALENDAR"""
    )

    # Confirm it exists
    results = cal.search(
        start=datetime.datetime(2026, 9, 15),
        end=datetime.datetime(2026, 9, 16),
        event=True,
    )
    assert len(results) == 1
    assert str(results[0].icalendar_component.get("UID")) == "test-delete-1"

    # Delete it
    results[0].delete()

    # Confirm it is gone
    results = cal.search(
        start=datetime.datetime(2026, 9, 15),
        end=datetime.datetime(2026, 9, 16),
        event=True,
    )
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Malformed iCal error case
# ---------------------------------------------------------------------------


def test_malformed_ical_raises_error(caldav_client: Any) -> None:
    """Sending invalid iCal data should raise an error from the server."""
    from caldav.lib.error import DAVError

    principal = caldav_client.principal()
    calendars = principal.calendars()
    cal = calendars[0]

    # VEVENT without DTSTART — Radicale rejects this with 400.
    missing_dtstart = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:test-bad-1
SUMMARY:No Start Date
END:VEVENT
END:VCALENDAR"""

    with pytest.raises(DAVError):
        cal.save_event(missing_dtstart)

    # Completely garbled data — Radicale cannot parse this as iCal.
    with pytest.raises(DAVError):
        cal.save_event("NOT A VALID ICALENDAR STRING AT ALL")
