"""Unit tests for add_to_calendar_handler — no agent dispatch layer."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from robotsix_calendar_agent.add_to_calendar_handler import (
    ERROR_INVALID_DATES,
    ERROR_MISSING_DATES,
    ERROR_MISSING_SUBJECT,
    _build_error_body,
    _event_to_dict,
    handle_add_to_calendar,
)
from robotsix_calendar_agent.caldav_client import CalendarEvent, OperationError
from tests.conftest import _mock_agent_comm_protocol

# ---------------------------------------------------------------------------
# Helpers (no fixtures needed — pure functions + MagicMock)
# ---------------------------------------------------------------------------


def _make_payload(**overrides: object) -> dict[str, Any]:
    """Build a valid add_to_calendar payload dict with overridable fields."""
    defaults: dict[str, Any] = {
        "subject": "Test Subject",
        "body_text": "Some body",
        "suggested_dtstart": "2026-03-15T09:00:00",
        "suggested_dtend": "2026-03-15T10:00:00",
        "description": "Test Description",
        "location": "Office",
        "correlation_id": "corr-unit-1",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# _build_error_body
# ---------------------------------------------------------------------------


class TestBuildErrorBody:
    def test_constructs_error_dict(self) -> None:
        result = _build_error_body("test_code", "Test message", "corr-abc")
        assert result == {
            "error": {"code": "test_code", "message": "Test message"},
            "correlation_id": "corr-abc",
        }

    def test_empty_correlation_id(self) -> None:
        result = _build_error_body("x", "y", "")
        assert result["correlation_id"] == ""

    def test_empty_message(self) -> None:
        result = _build_error_body("code", "", "cid")
        assert result["error"]["message"] == ""


# ---------------------------------------------------------------------------
# _event_to_dict
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _parse_and_validate_iso_dates
# ---------------------------------------------------------------------------


class TestParseAndValidateIsoDates:
    """Direct unit tests for _parse_and_validate_iso_dates()."""

    def _make_request(self) -> MagicMock:
        return MagicMock()

    def test_success_returns_dtstart_dtend_tuple(self) -> None:
        from datetime import datetime

        from robotsix_calendar_agent.add_to_calendar_handler import (
            _parse_and_validate_iso_dates,
        )

        request = self._make_request()
        result = _parse_and_validate_iso_dates(
            "2026-03-15T09:00:00",
            "2026-03-15T10:00:00",
            "corr-1",
            request,
        )
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == datetime(2026, 3, 15, 9, 0, 0)
        assert result[1] == datetime(2026, 3, 15, 10, 0, 0)

    def test_invalid_dtstart_returns_error_response(self) -> None:
        from robotsix_calendar_agent.add_to_calendar_handler import (
            _parse_and_validate_iso_dates,
        )

        request = self._make_request()
        result = _parse_and_validate_iso_dates(
            "not-a-date",
            "2026-03-15T10:00:00",
            "corr-2",
            request,
        )
        assert not isinstance(result, tuple)
        # It's a Response; verify the body through the call args on the mock
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES
        assert body["correlation_id"] == "corr-2"

    def test_invalid_dtend_returns_error_response(self) -> None:
        from robotsix_calendar_agent.add_to_calendar_handler import (
            _parse_and_validate_iso_dates,
        )

        request = self._make_request()
        result = _parse_and_validate_iso_dates(
            "2026-03-15T09:00:00",
            "garbage",
            "corr-3",
            request,
        )
        assert not isinstance(result, tuple)
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_dtend_before_dtstart_returns_error_response(self) -> None:
        from robotsix_calendar_agent.add_to_calendar_handler import (
            _parse_and_validate_iso_dates,
        )

        request = self._make_request()
        result = _parse_and_validate_iso_dates(
            "2026-03-15T10:00:00",
            "2026-03-15T09:00:00",
            "corr-4",
            request,
        )
        assert not isinstance(result, tuple)
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_dtend_equal_to_dtstart_returns_error_response(self) -> None:
        from robotsix_calendar_agent.add_to_calendar_handler import (
            _parse_and_validate_iso_dates,
        )

        request = self._make_request()
        result = _parse_and_validate_iso_dates(
            "2026-03-15T09:00:00",
            "2026-03-15T09:00:00",
            "corr-5",
            request,
        )
        assert not isinstance(result, tuple)
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_type_error_parsing_returns_error_response(self) -> None:
        from robotsix_calendar_agent.add_to_calendar_handler import (
            _parse_and_validate_iso_dates,
        )

        request = self._make_request()
        result = _parse_and_validate_iso_dates(
            12345,  # type: ignore[arg-type]
            "2026-03-15T10:00:00",
            "corr-6",
            request,
        )
        assert not isinstance(result, tuple)
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES


# ---------------------------------------------------------------------------
# handle_add_to_calendar — unit tests (direct call, no agent)
# ---------------------------------------------------------------------------


class TestHandleAddToCalendar:
    """Direct unit tests for handle_add_to_calendar().

    Mock the CalDAV client; call the handler function directly
    (bypassing CalendarAgent._handle_request).
    """

    # -- success -------------------------------------------------------

    def test_success_creates_event_and_returns_response(self) -> None:
        caldav_client = MagicMock()
        created_event = MagicMock(
            uid="evt-1",
            summary="Test Subject",
            description="Test Description",
            location="Office",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        caldav_client.create_event.return_value = created_event

        request = MagicMock()
        payload = _make_payload(correlation_id="corr-succ")

        handle_add_to_calendar(caldav_client, request, payload)

        caldav_client.create_event.assert_called_once()
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["correlation_id"] == "corr-succ"
        assert body["result"]["status"] == "created"
        assert body["result"]["event"]["uid"] == "evt-1"
        assert "confirmation_text" in body["result"]
        assert "Test Subject" in body["result"]["confirmation_text"]

    # -- non-dict payload ----------------------------------------------

    def test_non_dict_payload_returns_internal_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()

        handle_add_to_calendar(caldav_client, request, ["not", "a", "dict"])  # type: ignore[arg-type]

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == "internal_error"
        assert "must be a dictionary" in body["error"]["message"]
        assert body["correlation_id"] == ""

    def test_empty_dict_payload_returns_missing_subject(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()

        handle_add_to_calendar(caldav_client, request, {})

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT
        assert body["correlation_id"] == ""  # no correlation_id in empty dict

    # -- missing subject -----------------------------------------------

    def test_missing_subject_returns_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(subject="", correlation_id="corr-ms")

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT
        assert body["correlation_id"] == "corr-ms"

    def test_whitespace_only_subject_returns_missing_subject(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(subject="   \t  ", correlation_id="corr-ws")

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT

    def test_subject_missing_key_returns_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload()
        del payload["subject"]

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT

    def test_subject_not_a_string_returns_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(subject=12345, correlation_id="corr-ns")

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT

    # -- missing dates -------------------------------------------------

    def test_missing_dates_returns_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(
            suggested_dtstart="",
            suggested_dtend="",
            correlation_id="corr-md",
        )

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES
        assert body["correlation_id"] == "corr-md"

    def test_empty_dtstart_returns_missing_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(suggested_dtstart="", correlation_id="corr-ds")

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    def test_dates_missing_keys_returns_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload()
        del payload["suggested_dtstart"]
        del payload["suggested_dtend"]

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    def test_dates_not_strings_return_error(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(
            suggested_dtstart=20260315,
            suggested_dtend=20260316,
            correlation_id="corr-ns2",
        )

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    # -- invalid dates -------------------------------------------------

    def test_invalid_date_string_returns_invalid_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(
            suggested_dtstart="not-a-date",
            correlation_id="corr-id",
        )

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_dtend_before_dtstart_returns_invalid_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(
            suggested_dtstart="2026-03-15T10:00:00",
            suggested_dtend="2026-03-15T09:00:00",
            correlation_id="corr-bo",
        )

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_dtend_equal_to_dtstart_returns_invalid_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = _make_payload(
            suggested_dtstart="2026-03-15T09:00:00",
            suggested_dtend="2026-03-15T09:00:00",
            correlation_id="corr-eq",
        )

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    # -- CalDAV OperationError -----------------------------------------

    def test_operation_error_propagates_code(self) -> None:
        caldav_client = MagicMock()
        caldav_client.create_event.side_effect = OperationError(
            code="auth_failed", message="Authentication failed"
        )
        request = MagicMock()
        payload = _make_payload(correlation_id="corr-oe")

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == "auth_failed"
        assert body["error"]["message"] == "Authentication failed"
        assert body["correlation_id"] == "corr-oe"

    # -- generic Exception ---------------------------------------------

    def test_unexpected_exception_returns_internal_error(self) -> None:
        caldav_client = MagicMock()
        caldav_client.create_event.side_effect = RuntimeError("boom")
        request = MagicMock()
        payload = _make_payload(correlation_id="corr-ue")

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == "internal_error"
        assert "boom" in body["error"]["message"]
        assert body["correlation_id"] == "corr-ue"

    # -- correlation_id edge cases -------------------------------------

    def test_correlation_id_echoed_on_success(self) -> None:
        caldav_client = MagicMock()
        created_event = MagicMock(
            uid="evt-y",
            summary="S",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        caldav_client.create_event.return_value = created_event
        request = MagicMock()
        payload = _make_payload(
            subject="S",
            description="",
            location="",
            correlation_id="my-custom-id",
        )

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["correlation_id"] == "my-custom-id"

    def test_missing_correlation_id_echoes_empty_string(self) -> None:
        caldav_client = MagicMock()
        created_event = MagicMock(
            uid="evt-z",
            summary="S",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        caldav_client.create_event.return_value = created_event
        request = MagicMock()
        payload = _make_payload(
            subject="S",
            description="",
            location="",
        )
        del payload["correlation_id"]

        handle_add_to_calendar(caldav_client, request, payload)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["correlation_id"] == ""
