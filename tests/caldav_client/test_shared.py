"""Unit tests for _shared.py helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from robotsix_calendar_agent.caldav_client import CalendarEvent
from robotsix_calendar_agent.caldav_client._shared import _event_to_dict


class TestEventToDict:
    def test_converts_calendar_event_to_dict(self) -> None:
        event = CalendarEvent(
            uid="evt-1",
            summary="Lunch",
            description="Team lunch",
            location="Cafeteria",
            dtstart="2026-06-01T12:00:00",
            dtend="2026-06-01T13:00:00",
            calendar_id="personal",
        )
        result = _event_to_dict(event)
        assert result == {
            "uid": "evt-1",
            "summary": "Lunch",
            "description": "Team lunch",
            "location": "Cafeteria",
            "dtstart": "2026-06-01T12:00:00",
            "dtend": "2026-06-01T13:00:00",
            "calendar_id": "personal",
        }

    def test_default_fields_are_empty_strings(self) -> None:
        event = CalendarEvent(
            summary="Minimal",
            dtstart="2026-01-01T00:00:00",
            dtend="2026-01-01T01:00:00",
        )
        result = _event_to_dict(event)
        assert result["uid"] == ""
        assert result["description"] == ""
        assert result["location"] == ""
        assert result["calendar_id"] == ""

    def test_converts_magic_mock_event(self) -> None:
        mock_event = MagicMock(
            uid="muid",
            summary="MS",
            description="MD",
            location="ML",
            dtstart="2026-01-01T00:00:00",
            dtend="2026-01-01T01:00:00",
            calendar_id="Mcal",
        )
        result = _event_to_dict(mock_event)
        assert result["uid"] == "muid"
        assert result["summary"] == "MS"
