"""Unit tests for _shared.py helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from robotsix_calendar_agent.caldav_client import CalDavClient, CalendarEvent
from robotsix_calendar_agent.caldav_client._shared import (
    _event_to_dict,
    _is_transient_exception,
    _unescape_text,
)


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


class TestIsTransientException:
    """Verify that ``_is_transient_exception`` correctly classifies
    exceptions as retryable or non-retryable."""

    # -- retryable by type --------------------------------------------------

    def test_connection_error_is_transient(self) -> None:
        assert _is_transient_exception(ConnectionError("connection refused"))

    def test_timeout_error_is_transient(self) -> None:
        assert _is_transient_exception(TimeoutError("timed out"))

    # -- retryable by message substring ------------------------------------

    @pytest.mark.parametrize(
        "message",
        [
            "Connection refused",
            "Connection Refused",
            "CONNECTION REFUSED",
            "Connection reset by peer",
            "Request timeout",
            "timed out after 30s",
            "name or service not known",
            "Temporary failure in name resolution",
            "ECONNREFUSED",
            "ECONNRESET",
            "EOF occurred in violation of protocol",
            "broken pipe",
        ],
    )
    def test_retryable_message_patterns(self, message: str) -> None:
        exc = Exception(message)
        assert _is_transient_exception(exc), f"expected True for {message!r}"

    # -- non-retryable ------------------------------------------------------

    def test_value_error_not_transient(self) -> None:
        assert not _is_transient_exception(ValueError("invalid value"))

    def test_key_error_not_transient(self) -> None:
        assert not _is_transient_exception(KeyError("missing key"))

    def test_generic_exception_not_transient(self) -> None:
        assert not _is_transient_exception(Exception("something went wrong"))

    def test_unrelated_message_not_transient(self) -> None:
        assert not _is_transient_exception(Exception("404 not found"))


class TestUnescapeText:
    """Verify that ``_unescape_text`` correctly reverses ``_escape_text``,
    including edge cases around the sentinel replacement logic."""

    # -- round-trip with _escape_text ---------------------------------------

    @pytest.mark.parametrize(
        "original",
        [
            "",
            "plain text",
            r"back\slash",
            "semi;colon",
            "comma,text",
            "line\nbreak",
            "a\\b;c,d\ne",
            # text that is already partially escaped should survive round-trip
            # through the CalDavClient._escape_text → _unescape_text pair
            "text with \\ backslash",
        ],
    )
    def test_round_trip(self, client: CalDavClient, original: str) -> None:
        """_escape_text → _unescape_text restores the original string."""
        escaped = client._escape_text(original)
        assert _unescape_text(escaped) == original

    # -- edge cases ---------------------------------------------------------

    def test_empty_string(self) -> None:
        assert _unescape_text("") == ""

    def test_plain_text_no_escapes(self) -> None:
        assert _unescape_text("hello world") == "hello world"

    def test_mixed_escapes(self) -> None:
        escaped = r"a\\b\;c\,d\ne\\f"
        expected = "a\\b;c,d\ne\\f"
        assert _unescape_text(escaped) == expected

    def test_sentinel_logic_backslash_before_semicolon(self) -> None:
        r"""When ``\\`` appears before ``\;`` in the escaped text,
        the sentinel prevents the backslash from being consumed
        by the semicolon unescape step."""
        # r"\\\;" → literal "\\\;" → _unescape → "\;"
        escaped = r"\\\;"
        expected = "\\;"
        assert _unescape_text(escaped) == expected

    def test_consecutive_escaped_backslashes(self) -> None:
        escaped = r"\\\\"
        expected = "\\\\"
        assert _unescape_text(escaped) == expected

    def test_already_unescaped_text_is_idempotent(self) -> None:
        """Passing already-unescaped text should not corrupt it."""
        text = "plain text with no escapes"
        assert _unescape_text(text) == text
