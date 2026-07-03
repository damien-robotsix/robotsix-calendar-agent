"""Unit tests for add_to_calendar_handler — no agent dispatch layer."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from robotsix_calendar_agent.add_to_calendar_handler import (
    ERROR_INVALID_DATES,
    ERROR_MISSING_DATES,
    ERROR_MISSING_SUBJECT,
    _build_error_body,
    _build_resolution_instruction,
    _event_to_dict,
    _resolve_dates_via_llm,
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


# ---------------------------------------------------------------------------
# _build_resolution_instruction
# ---------------------------------------------------------------------------


class TestBuildResolutionInstruction:
    def test_full_context_formats_correctly(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Team Lunch",
            body_text="Let's meet at noon.",
            email_date="2026-03-15",
            extracted_dates=["2026-03-20", "noon"],
        )
        assert "Team Lunch" in instruction
        assert "Email subject: Team Lunch" in instruction
        assert "Email date: 2026-03-15" in instruction
        assert "Date/time references found: 2026-03-20, noon" in instruction
        assert "Let's meet at noon." in instruction
        assert "Email body:" in instruction
        assert "Resolve a concrete start and end datetime in ISO 8601" in instruction
        assert "default the end to one hour after the start" in instruction

    def test_minimal_context_no_optional_fields(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Quick Call",
            body_text="",
            email_date="",
            extracted_dates=[],
        )
        assert "Email subject: Quick Call" in instruction
        assert "Email date:" not in instruction
        assert "Date/time references found:" not in instruction
        assert "Email body:" not in instruction
        assert "Resolve a concrete start and end datetime in ISO 8601" in instruction

    def test_body_text_without_email_date_or_extracted_dates(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Reminder",
            body_text="Don't forget!",
            email_date="",
            extracted_dates=[],
        )
        assert "Email subject: Reminder" in instruction
        assert "Email date:" not in instruction
        assert "Date/time references found:" not in instruction
        assert "Email body:" in instruction
        assert "Don't forget!" in instruction

    def test_email_date_without_body_or_extracted_dates(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Event",
            body_text="",
            email_date="2026-06-01",
            extracted_dates=[],
        )
        assert "Email subject: Event" in instruction
        assert "Email date: 2026-06-01" in instruction
        assert "Date/time references found:" not in instruction
        assert "Email body:" not in instruction

    def test_extracted_dates_without_body_or_email_date(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Booking",
            body_text="",
            email_date="",
            extracted_dates=["Monday", "3pm"],
        )
        assert "Email subject: Booking" in instruction
        assert "Email date:" not in instruction
        assert "Date/time references found: Monday, 3pm" in instruction
        assert "Email body:" not in instruction

    def test_description_included_when_present(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Team Lunch",
            body_text="Let's meet at noon.",
            email_date="2026-03-15",
            extracted_dates=["2026-03-20"],
            description="Monthly team gathering",
        )
        assert "Description: Monthly team gathering" in instruction

    def test_location_included_when_present(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Team Lunch",
            body_text="Let's meet at noon.",
            email_date="2026-03-15",
            extracted_dates=["2026-03-20"],
            location="Conference Room B",
        )
        assert "Location: Conference Room B" in instruction

    def test_description_and_location_both_included(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Team Lunch",
            body_text="Let's meet at noon.",
            email_date="2026-03-15",
            extracted_dates=["2026-03-20"],
            description="Monthly team gathering",
            location="Conference Room B",
        )
        assert "Description: Monthly team gathering" in instruction
        assert "Location: Conference Room B" in instruction
        # Verify description and location appear before email_date
        desc_idx = instruction.index("Description:")
        loc_idx = instruction.index("Location:")
        ed_idx = instruction.index("Email date:")
        assert desc_idx < ed_idx
        assert loc_idx < ed_idx

    def test_empty_description_and_location_not_included(self) -> None:
        instruction = _build_resolution_instruction(
            subject="Team Lunch",
            body_text="Let's meet at noon.",
            email_date="2026-03-15",
            extracted_dates=["2026-03-20"],
            description="",
            location="",
        )
        assert "Description:" not in instruction
        assert "Location:" not in instruction


# ---------------------------------------------------------------------------
# _resolve_dates_via_llm (direct)
# ---------------------------------------------------------------------------


class TestResolveDatesViaLlmDirect:
    """Direct unit tests for _resolve_dates_via_llm()."""

    def test_returns_none_when_intent_parser_is_none(self) -> None:
        payload: dict[str, Any] = {
            "subject": "Test",
            "body_text": "Body",
        }
        result = _resolve_dates_via_llm(None, payload)
        assert result is None

    def test_successful_resolution_returns_dtstart_dtend(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {
            "dtstart": "2026-06-01T12:00:00",
            "dtend": "2026-06-01T13:00:00",
        }
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {
            "subject": "Lunch",
            "body_text": "Let's eat.",
            "email_date": "2026-05-30",
            "extracted_dates": ["June 1st"],
        }
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result == ("2026-06-01T12:00:00", "2026-06-01T13:00:00")

    def test_non_create_event_operation_returns_none(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "list_events"
        parsed.params = {}
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_parser_raises_exception_returns_none(self) -> None:
        intent_parser = MagicMock()
        intent_parser.parse.side_effect = RuntimeError("LLM unavailable")

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_missing_dtstart_in_params_returns_none(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {"dtend": "2026-06-01T13:00:00"}
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_missing_dtend_in_params_returns_none(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {"dtstart": "2026-06-01T12:00:00"}
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_empty_dtstart_string_returns_none(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {
            "dtstart": "",
            "dtend": "2026-06-01T13:00:00",
        }
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_empty_dtend_string_returns_none(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {
            "dtstart": "2026-06-01T12:00:00",
            "dtend": "",
        }
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_none_params_returns_none(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = None
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_missing_operation_attribute_returns_none(self) -> None:
        intent_parser = MagicMock()
        # spec=[] allows only intrinsic mock attributes — accessing .operation
        # raises AttributeError, which getattr() in the production code
        # catches and defaults to "", causing the != "create_event" guard
        # to return None.
        parsed = MagicMock(spec=[])
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {"subject": "Test"}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result is None

    def test_missing_payload_keys_default_safely(self) -> None:
        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {
            "dtstart": "2026-06-01T12:00:00",
            "dtend": "2026-06-01T13:00:00",
        }
        intent_parser.parse.return_value = parsed

        payload: dict[str, Any] = {}
        result = _resolve_dates_via_llm(intent_parser, payload)
        assert result == ("2026-06-01T12:00:00", "2026-06-01T13:00:00")
        # Verify the instruction was built with empty defaults
        call_arg = intent_parser.parse.call_args[0][0]
        assert "Email subject: " in call_arg
        assert "Email date:" not in call_arg
        assert "Date/time references found:" not in call_arg
        assert "Email body:" not in call_arg


# ---------------------------------------------------------------------------
# handle_add_to_calendar — LLM date resolution (integrated)
# ---------------------------------------------------------------------------


class TestHandleAddToCalendarLlm:
    """Tests for handle_add_to_calendar() exercising the LLM fallback path.

    These tests supply an intent_parser mock and omit explicit
    suggested_dtstart / suggested_dtend so the handler must resolve
    dates via the LLM path.
    """

    def _make_llm_payload(self, **overrides: object) -> dict[str, Any]:
        """Build a payload WITHOUT explicit dates so the LLM path is used."""
        base: dict[str, Any] = {
            "subject": "Team Lunch",
            "body_text": "Let's meet at noon.",
            "email_date": "2026-03-15",
            "extracted_dates": ["2026-03-20", "noon"],
            "correlation_id": "corr-llm",
        }
        base.update(overrides)
        return base

    def _make_successful_parser(self) -> MagicMock:
        """Return an intent_parser mock that resolves dates successfully."""
        parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {
            "dtstart": "2026-06-01T12:00:00",
            "dtend": "2026-06-01T13:00:00",
        }
        parser.parse.return_value = parsed
        return parser

    def test_llm_resolution_success_creates_event(self) -> None:
        caldav_client = MagicMock()
        created_event = MagicMock(
            uid="evt-llm-1",
            summary="Team Lunch",
            description="",
            location="",
            dtstart="2026-06-01T12:00:00",
            dtend="2026-06-01T13:00:00",
            calendar_id="cal",
        )
        caldav_client.create_event.return_value = created_event
        request = MagicMock()
        payload = self._make_llm_payload()
        intent_parser = self._make_successful_parser()

        handle_add_to_calendar(
            caldav_client, request, payload, intent_parser=intent_parser
        )

        # Verify the parser was called with an instruction containing payload context
        intent_parser.parse.assert_called_once()
        instruction = intent_parser.parse.call_args[0][0]
        assert "Team Lunch" in instruction
        assert "2026-03-15" in instruction

        # Verify a calendar event was created with the resolved dates
        caldav_client.create_event.assert_called_once()
        event_arg = caldav_client.create_event.call_args[0][0]
        assert event_arg.dtstart == "2026-06-01T12:00:00"
        assert event_arg.dtend == "2026-06-01T13:00:00"

        # Verify success response
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["correlation_id"] == "corr-llm"
        assert body["result"]["status"] == "created"
        assert body["result"]["event"]["uid"] == "evt-llm-1"

    def test_non_create_event_operation_falls_back_to_missing_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = self._make_llm_payload()

        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "list_events"
        parsed.params = {}
        intent_parser.parse.return_value = parsed

        handle_add_to_calendar(
            caldav_client, request, payload, intent_parser=intent_parser
        )

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES
        assert body["correlation_id"] == "corr-llm"

    def test_parser_raises_exception_falls_back_to_missing_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = self._make_llm_payload()

        intent_parser = MagicMock()
        intent_parser.parse.side_effect = RuntimeError("LLM down")

        handle_add_to_calendar(
            caldav_client, request, payload, intent_parser=intent_parser
        )

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    def test_missing_dtstart_in_params_falls_back_to_missing_dates(self) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = self._make_llm_payload()

        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        parsed.params = {"dtend": "2026-06-01T13:00:00"}
        intent_parser.parse.return_value = parsed

        handle_add_to_calendar(
            caldav_client, request, payload, intent_parser=intent_parser
        )

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    def test_intent_parser_none_without_explicit_dates_returns_missing_dates(
        self,
    ) -> None:
        caldav_client = MagicMock()
        request = MagicMock()
        payload = self._make_llm_payload()

        # Explicitly pass intent_parser=None (the default)
        handle_add_to_calendar(caldav_client, request, payload, intent_parser=None)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    def test_llm_dates_still_validated_for_iso_and_ordering(self) -> None:
        """LLM-resolved dates still go through ISO parsing and dtend>dtstart check."""
        caldav_client = MagicMock()
        request = MagicMock()
        payload = self._make_llm_payload()

        intent_parser = MagicMock()
        parsed = MagicMock()
        parsed.operation = "create_event"
        # dtend before dtstart — should fail validation
        parsed.params = {
            "dtstart": "2026-06-01T13:00:00",
            "dtend": "2026-06-01T12:00:00",
        }
        intent_parser.parse.return_value = parsed

        handle_add_to_calendar(
            caldav_client, request, payload, intent_parser=intent_parser
        )

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_llm_resolution_with_explicit_dates_skips_llm(self) -> None:
        """When explicit dates are present, the LLM path is skipped entirely."""
        caldav_client = MagicMock()
        created_event = MagicMock(
            uid="evt-explicit",
            summary="Test",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        caldav_client.create_event.return_value = created_event
        request = MagicMock()
        payload = _make_payload()  # has explicit suggested_dtstart/dtend

        intent_parser = MagicMock()
        # intent_parser.parse should never be called
        handle_add_to_calendar(
            caldav_client, request, payload, intent_parser=intent_parser
        )

        intent_parser.parse.assert_not_called()
        call_args = _mock_agent_comm_protocol.Response.to.call_args
        body = call_args[1]["body"]
        assert body["result"]["status"] == "created"
