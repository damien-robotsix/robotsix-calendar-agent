"""Tests for CalendarAgent — all external deps mocked."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Shared helpers and module-level mocks live in conftest.
from tests.conftest import (
    _mock_agent_comm_protocol,
    _mock_agent_comm_sdk,
    _mock_agent_comm_transport,
    caldav_contact,
    caldav_event,
    caldav_task,
    make_request,
    setup_mocks,
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCalendarAgentInit:
    def test_creates_with_env_vars(self) -> None:
        setup_mocks()

        os.environ["RADICALE_URL"] = "https://x.com"
        os.environ["RADICALE_USERNAME"] = "u"
        os.environ["RADICALE_PASSWORD"] = "p"

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            agent = CalendarAgent()
            assert agent._agent_id == "calendar"

    def test_raises_value_error_for_missing_credentials(self) -> None:
        setup_mocks()

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            with pytest.raises(ValueError, match="credentials"):
                CalendarAgent()


class TestHandleRequest:
    def test_valid_instruction_returns_response(
        self, calendar_agent: MagicMock
    ) -> None:
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="list_events",
            params={"start": "2026-01-01", "end": "2026-01-07"},
            original_text="list events this week",
        )

        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.list_events.return_value = [
            MagicMock(
                uid="evt-1",
                summary="Test",
                description="",
                location="",
                dtstart="2026-01-02",
                dtend="2026-01-02",
                calendar_id="cal",
            )
        ]

        req = make_request({"instruction": "list events this week"})
        result = calendar_agent._handle_request(req)

        assert result is not None
        _mock_agent_comm_protocol.Response.to.assert_called()
        # The response must carry a human-readable ``reply`` (the agent-comm
        # convention read by reply_text) alongside the structured ``result`` —
        # without it, generic consumers like robotsix-chat see an empty reply.
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"][0]["uid"] == "evt-1"
        reply = kwargs["body"]["reply"]
        assert isinstance(reply, str) and reply
        assert "Found 1" in reply and "Test" in reply

    def test_missing_instruction_returns_error(self, calendar_agent: MagicMock) -> None:
        req = make_request({"not_instruction": "x"})
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "missing_instruction"

    def test_parse_error_returns_error(self, calendar_agent: MagicMock) -> None:
        from robotsix_calendar_agent.intent_parser import IntentParseError

        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.side_effect = IntentParseError("bad input")

        req = make_request({"instruction": "gibberish"})
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "parse_error"

    def test_operation_error_returns_error(self, calendar_agent: MagicMock) -> None:
        from robotsix_calendar_agent.caldav_client import OperationError

        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="delete_event",
            params={"uid": "evt-1"},
        )

        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.delete_event.side_effect = OperationError(
            code="not_found", message="Event not found"
        )

        req = make_request({"instruction": "delete event evt-1"})
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "not_found"

    def test_agent_registers_as_calendar(self) -> None:
        setup_mocks()

        os.environ["RADICALE_URL"] = "https://x.com"
        os.environ["RADICALE_USERNAME"] = "u"
        os.environ["RADICALE_PASSWORD"] = "p"

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            CalendarAgent(agent_id="calendar")

            # In-process default: builds an Agent over a fresh Registry.
            _mock_agent_comm_sdk.Agent.assert_called_with(
                "calendar",
                _mock_agent_comm_transport.Registry.return_value,
            )

    def test_provided_agent_is_used_and_handler_wired(self) -> None:
        # The brokered service passes a pre-built agent (a BrokeredAgent); the
        # CalendarAgent wires its request handler onto it instead of building
        # its own Agent.
        setup_mocks()

        os.environ["RADICALE_URL"] = "https://x.com"
        os.environ["RADICALE_USERNAME"] = "u"
        os.environ["RADICALE_PASSWORD"] = "p"

        provided = MagicMock(name="brokered_agent")
        _mock_agent_comm_sdk.Agent.reset_mock()

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            cal = CalendarAgent("robotsix-calendar", agent=provided)

            _mock_agent_comm_sdk.Agent.assert_not_called()
            provided.on_request.assert_called_once_with(cal._handle_request)

    def test_unexpected_exception_returns_internal_error(
        self, calendar_agent: MagicMock
    ) -> None:
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="delete_event",
            params={"uid": "evt-1"},
        )

        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.delete_event.side_effect = RuntimeError("boom")

        req = make_request({"instruction": "delete event evt-1"})
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "internal_error"

    def test_empty_body_returns_missing_instruction(
        self, calendar_agent: MagicMock
    ) -> None:
        req = MagicMock()
        req.body = None
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "missing_instruction"


# ---------------------------------------------------------------------------
# Dispatch — exercise every operation branch
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_create_event(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "Lunch",
                "dtstart": "2026-01-02T12:00:00",
                "dtend": "2026-01-02T13:00:00",
            },
        )
        calendar_agent._mock_caldav.create_event.return_value = caldav_event("new")

        calendar_agent._handle_request(make_request({"instruction": "add lunch"}))

        calendar_agent._mock_caldav.create_event.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"]["uid"] == "new"

    def test_update_event(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="update_event",
            params={"uid": "evt-1", "summary": "Updated"},
        )
        calendar_agent._mock_caldav.update_event.return_value = caldav_event("evt-1")

        calendar_agent._handle_request(make_request({"instruction": "update"}))

        calendar_agent._mock_caldav.update_event.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"]["uid"] == "evt-1"

    def test_update_event_missing_uid_key_returns_error(
        self, calendar_agent: MagicMock
    ) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="update_event",
            params={"summary": "Updated"},
        )

        calendar_agent._handle_request(make_request({"instruction": "update"}))

        calendar_agent._mock_caldav.update_event.assert_not_called()
        calendar_agent._mock_caldav.create_event.assert_not_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "missing_uid"

    def test_delete_event_returns_deleted_flag(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="delete_event",
            params={"uid": "evt-1"},
        )

        calendar_agent._handle_request(make_request({"instruction": "delete"}))

        calendar_agent._mock_caldav.delete_event.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"] == {"deleted": True}

    def test_list_contacts(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="list_contacts",
            params={},
        )
        calendar_agent._mock_caldav.list_contacts.return_value = [caldav_contact()]

        calendar_agent._handle_request(make_request({"instruction": "list contacts"}))

        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        result = kwargs["body"]["result"]
        assert result[0]["uid"] == "cnt-1"
        assert result[0]["full_name"] == "John Doe"

    def test_create_contact(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="create_contact",
            params={"full_name": "Jane", "email": "jane@example.com"},
        )
        calendar_agent._mock_caldav.create_contact.return_value = caldav_contact("new")

        calendar_agent._handle_request(make_request({"instruction": "add jane"}))

        calendar_agent._mock_caldav.create_contact.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"]["uid"] == "new"

    def test_update_contact(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="update_contact",
            params={"uid": "cnt-1", "email": "new@example.com"},
        )
        calendar_agent._mock_caldav.update_contact.return_value = caldav_contact(
            "cnt-1"
        )

        calendar_agent._handle_request(make_request({"instruction": "update jane"}))

        calendar_agent._mock_caldav.update_contact.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"]["uid"] == "cnt-1"

    def test_update_contact_missing_uid_key_returns_error(
        self, calendar_agent: MagicMock
    ) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="update_contact",
            params={"email": "new@example.com"},
        )

        calendar_agent._handle_request(make_request({"instruction": "update jane"}))

        calendar_agent._mock_caldav.update_contact.assert_not_called()
        calendar_agent._mock_caldav.create_contact.assert_not_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "missing_uid"

    def test_delete_contact_returns_deleted_flag(
        self, calendar_agent: MagicMock
    ) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="delete_contact",
            params={"uid": "cnt-1"},
        )

        calendar_agent._handle_request(make_request({"instruction": "remove jane"}))

        calendar_agent._mock_caldav.delete_contact.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        assert kwargs["body"]["result"] == {"deleted": True}

    def test_list_tasks(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="list_tasks",
            params={},
        )
        calendar_agent._mock_caldav.list_tasks.return_value = [
            caldav_task("task-1"),
            caldav_task("task-2"),
        ]

        calendar_agent._handle_request(make_request({"instruction": "show my tasks"}))

        calendar_agent._mock_caldav.list_tasks.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        result = kwargs["body"]["result"]
        assert len(result) == 2
        assert result[0]["uid"] == "task-1"
        assert result[0]["summary"] == "Buy milk"
        assert result[0]["status"] == "NEEDS-ACTION"

    def test_list_calendars(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="list_calendars",
            params={},
        )
        calendar_agent._mock_caldav.list_calendars.return_value = [
            "Robotsix",
            "Birthdays",
            "Damien",
        ]

        calendar_agent._handle_request(
            make_request({"instruction": "what calendars do I have?"})
        )

        calendar_agent._mock_caldav.list_calendars.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        result = kwargs["body"]["result"]
        assert result == ["Robotsix", "Birthdays", "Damien"]
        reply = kwargs["body"]["reply"]
        assert isinstance(reply, str) and reply
        assert "Found 3" in reply
        assert "Robotsix" in reply

    def test_unknown_operation_returns_error(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="frobnicate",
            params={},
        )

        calendar_agent._handle_request(make_request({"instruction": "frobnicate"}))

        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs.get("code") == "unknown_operation"


# ---------------------------------------------------------------------------
# Add-to-calendar (structured, no LLM)
# ---------------------------------------------------------------------------


class TestHandleAddToCalendar:
    # -- success path (explicit dates) ---------------------------------

    def test_valid_request_creates_event(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "Test Subject",
                "description": "Test Description",
                "location": "Office",
                "dtstart": "2026-03-15T09:00:00",
                "dtend": "2026-03-15T10:00:00",
            },
        )
        mock_caldav = calendar_agent._mock_caldav
        created_event = MagicMock(
            uid="evt-1",
            summary="Test Subject",
            description="Test Description",
            location="Office",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        mock_caldav.create_event.return_value = created_event

        req = make_add_to_calendar_request(correlation_id="corr-123")
        calendar_agent._handle_request(req)

        mock_parser.parse.assert_called_once()
        mock_caldav.create_event.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert body["result"]["uid"] == "evt-1"
        assert body["result"]["summary"] == "Test Subject"
        assert "reply" in body
        assert "Test Subject" in body["reply"]

    def test_instruction_includes_explicit_dates(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "S",
                "dtstart": "2026-03-15T09:00:00",
                "dtend": "2026-03-15T10:00:00",
            },
        )
        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.create_event.return_value = MagicMock(
            uid="evt-x",
            summary="S",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )

        req = make_add_to_calendar_request(
            subject="S",
            description="",
            location="",
            correlation_id="c",
        )
        calendar_agent._handle_request(req)

        # The synthetic instruction must embed the explicit datetimes.
        parse_call_arg = mock_parser.parse.call_args[0][0]
        assert "dtstart=2026-03-15T09:00:00" in parse_call_arg
        assert "dtend=2026-03-15T10:00:00" in parse_call_arg

    # -- error paths ---------------------------------------------------

    def test_parse_error_propagates(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        from robotsix_calendar_agent.intent_parser import IntentParseError

        calendar_agent._mock_parser.parse.side_effect = IntentParseError(
            "cannot parse"
        )
        req = make_add_to_calendar_request()
        calendar_agent._handle_request(req)

        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "parse_error"
        assert "cannot parse" in kwargs["message"]

    def test_operation_error_propagates_code(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import OperationError

        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "Test Subject",
                "dtstart": "2026-03-15T09:00:00",
                "dtend": "2026-03-15T10:00:00",
            },
        )
        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.create_event.side_effect = OperationError(
            code="auth_failed", message="Authentication failed"
        )

        req = make_add_to_calendar_request(correlation_id="corr-6")
        calendar_agent._handle_request(req)

        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "auth_failed"

    def test_unexpected_exception_returns_internal_error(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "Test Subject",
                "dtstart": "2026-03-15T09:00:00",
                "dtend": "2026-03-15T10:00:00",
            },
        )
        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.create_event.side_effect = RuntimeError("boom")

        req = make_add_to_calendar_request(correlation_id="corr-7")
        calendar_agent._handle_request(req)

        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "internal_error"

    # -- LLM date resolution (auto-mail's dateless payload) ------------

    def test_llm_resolves_dates_when_suggested_absent(
        self, calendar_agent: MagicMock
    ) -> None:
        # auto-mail forwards raw email context with no suggested_dt* fields.
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "Dentist",
                "dtstart": "2026-03-15T09:00:00",
                "dtend": "2026-03-15T10:00:00",
            },
        )
        created_event = MagicMock(
            uid="evt-llm",
            summary="Dentist appointment",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        calendar_agent._mock_caldav.create_event.return_value = created_event

        req = make_request(
            {
                "add_to_calendar": {
                    "subject": "Dentist appointment",
                    "body_text": "See you March 15 at 9am.",
                    "email_date": "2026-03-01",
                    "extracted_dates": ["March 15", "9am"],
                    "correlation_id": "corr-llm",
                }
            }
        )
        calendar_agent._handle_request(req)

        mock_parser.parse.assert_called_once()
        # Verify the resolution instruction carries the email context.
        parse_call_arg = mock_parser.parse.call_args[0][0]
        assert "Dentist appointment" in parse_call_arg
        assert "March 15" in parse_call_arg
        calendar_agent._mock_caldav.create_event.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert body["result"]["uid"] == "evt-llm"
        assert "reply" in body

    def test_llm_cannot_resolve_returns_parse_error(
        self, calendar_agent: MagicMock
    ) -> None:
        from robotsix_calendar_agent.intent_parser import IntentParseError

        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.side_effect = IntentParseError("cannot resolve dates")

        req = make_request(
            {
                "add_to_calendar": {
                    "subject": "No date here",
                    "body_text": "Just saying hi.",
                    "correlation_id": "corr-nodate",
                }
            }
        )
        calendar_agent._handle_request(req)

        calendar_agent._mock_caldav.create_event.assert_not_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "parse_error"

    def test_llm_instruction_includes_description_and_location(
        self, calendar_agent: MagicMock
    ) -> None:
        """Regression: ensure description & location are forwarded in
        the LLM-resolution instruction, not only the explicit-dates branch."""
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="create_event",
            params={
                "summary": "Meeting",
                "description": "Discuss roadmap",
                "location": "Room 42",
                "dtstart": "2026-06-30T14:00:00",
                "dtend": "2026-06-30T15:00:00",
            },
        )
        calendar_agent._mock_caldav.create_event.return_value = MagicMock(
            uid="evt-desc",
            summary="Meeting",
            description="Discuss roadmap",
            location="Room 42",
            dtstart="2026-06-30T14:00:00",
            dtend="2026-06-30T15:00:00",
            calendar_id="cal",
        )

        req = make_request(
            {
                "add_to_calendar": {
                    "subject": "Meeting",
                    "description": "Discuss roadmap",
                    "location": "Room 42",
                    "body_text": "Let's meet June 30 at 2pm.",
                    "email_date": "2026-06-28",
                    "correlation_id": "corr-desc",
                }
            }
        )
        calendar_agent._handle_request(req)

        parse_call_arg = mock_parser.parse.call_args[0][0]
        assert "Description: Discuss roadmap" in parse_call_arg
        assert "Location: Room 42" in parse_call_arg

    def test_add_to_calendar_with_wrong_operation_is_rejected(
        self, calendar_agent: MagicMock
    ) -> None:
        """Hardening: when add_to_calendar is present but the parser
        returns a non-create_event operation, the agent must reject it."""
        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.return_value = MagicMock(
            operation="list_events",
            params={},
        )

        req = make_request(
            {
                "add_to_calendar": {
                    "subject": "Some event",
                    "suggested_dtstart": "2026-06-30T09:00:00",
                    "suggested_dtend": "2026-06-30T10:00:00",
                    "correlation_id": "corr-badop",
                }
            }
        )
        calendar_agent._handle_request(req)

        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unexpected_operation"
        assert "create" in kwargs["message"]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_start_delegates_to_agent(self, calendar_agent: MagicMock) -> None:
        calendar_agent.start()
        calendar_agent._mock_agent_comm.start.assert_called_once()

    def test_stop_delegates_to_agent(self, calendar_agent: MagicMock) -> None:
        calendar_agent.stop()
        calendar_agent._mock_agent_comm.stop.assert_called_once()

    def test_context_manager(self, calendar_agent: MagicMock) -> None:
        with calendar_agent as ctx:
            assert ctx is calendar_agent
        calendar_agent._mock_agent_comm.start.assert_called_once()
        calendar_agent._mock_agent_comm.stop.assert_called_once()


# ---------------------------------------------------------------------------
# Dispatch-enum consistency
# ---------------------------------------------------------------------------


class TestDispatchEnumSync:
    """Verify _DISPATCH keys stay in sync with all operation enums."""

    def test_dispatch_keys_match_enum_values(self) -> None:
        from robotsix_calendar_agent.agent import _DISPATCH
        from robotsix_calendar_agent.intent_parser import (
            CalendarOperation,
            ContactOperation,
            TaskOperation,
        )

        dispatch_keys = set(_DISPATCH)
        enum_values = (
            {m.value for m in CalendarOperation}
            | {m.value for m in ContactOperation}
            | {m.value for m in TaskOperation}
        )
        assert dispatch_keys == enum_values, (
            f"Mismatch: extra in dict={dispatch_keys - enum_values}, "
            f"missing={enum_values - dispatch_keys}"
        )


# ---------------------------------------------------------------------------
# Telemetry counters
# ---------------------------------------------------------------------------


class TestTelemetry:
    def test_counters_initialise_to_zero(self, calendar_agent: MagicMock) -> None:
        assert calendar_agent._request_count == 0
        assert calendar_agent._error_count == 0
        assert calendar_agent._in_flight == 0
        assert calendar_agent._started_at is not None
        assert calendar_agent._last_request_ts is None

    def test_request_increments_counter(self, calendar_agent: MagicMock) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="list_calendars",
            params={},
        )
        calendar_agent._mock_caldav.list_calendars.return_value = ["Cal"]

        req = make_request({"instruction": "list calendars"})
        calendar_agent._handle_request(req)

        assert calendar_agent._request_count == 1
        assert calendar_agent._last_request_ts is not None
        assert calendar_agent._in_flight == 0  # finally decremented

    def test_error_increments_error_counter(self, calendar_agent: MagicMock) -> None:
        # Error responses (caught exceptions converted to Error messages)
        # should increment the error counter.
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="delete_event",
            params={"uid": "evt-1"},
        )
        calendar_agent._mock_caldav.delete_event.side_effect = RuntimeError("boom")

        req = make_request({"instruction": "delete event evt-1"})
        calendar_agent._handle_request(req)

        assert calendar_agent._error_count == 1
        assert calendar_agent._request_count == 1
        assert calendar_agent._in_flight == 0

    def test_monitor_snapshot_contains_live_counters(
        self, calendar_agent: MagicMock
    ) -> None:
        calendar_agent._mock_parser.parse.return_value = MagicMock(
            operation="list_calendars",
            params={},
        )
        calendar_agent._mock_caldav.list_calendars.return_value = ["Cal"]
        calendar_agent._mock_caldav.health.return_value = {
            "connected": True,
            "calendar_count": 1,
        }
        calendar_agent._mock_caldav._url = "https://rad.example.com"
        calendar_agent._mock_caldav._default_calendar = "TestCal"

        req = make_request({"instruction": "list calendars"})
        calendar_agent._handle_request(req)

        snap = calendar_agent.monitor_snapshot()
        assert snap["agent_id"] == "calendar"
        assert snap["request_count"] == 1
        assert snap["error_count"] == 0
        assert snap["in_flight"] == 0
        assert isinstance(snap["uptime_seconds"], float)
        assert snap["uptime_seconds"] >= 0
        assert snap["caldav_health"]["connected"] is True
        assert snap["caldav_health"]["calendar_count"] == 1


# ---------------------------------------------------------------------------
# _summarize_item unit tests
# ---------------------------------------------------------------------------


class TestSummarizeItem:
    def test_bare_string_passthrough(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        assert _summarize_item("hello") == "hello"  # type: ignore[arg-type]

    def test_task_with_due_and_status(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item(
            {
                "summary": "Buy milk",
                "due": "2026-06-21",
                "status": "NEEDS-ACTION",
                "uid": "t1",
            }
        )
        assert result == "Buy milk due 2026-06-21 [NEEDS-ACTION] [uid=t1]"

    def test_task_without_uid(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"due": "2026-06-21"})
        assert result == "(untitled) due 2026-06-21"

    def test_task_untitled_no_fields(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"due": "2026-06-21", "uid": "t2"})
        assert "(untitled)" in result
        assert "[uid=t2]" in result

    def test_event_with_summary_and_dtstart_and_location(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item(
            {
                "summary": "Lunch",
                "dtstart": "2026-01-02T12:00:00",
                "location": "Office",
                "uid": "e1",
            }
        )
        assert result == "Lunch at 2026-01-02T12:00:00 (Office) [uid=e1]"

    def test_event_without_uid(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"summary": "Meeting", "dtstart": "2026-07-01"})
        assert result == "Meeting at 2026-07-01"

    def test_event_without_dtstart_summary_fallback(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"summary": "No time event"})
        assert result == "No time event"

    def test_contact_with_name_and_email(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"full_name": "Jane Doe", "email": "jane@example.com"})
        assert result == "Jane Doe <jane@example.com>"

    def test_contact_without_email(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"full_name": "Jane Doe"})
        assert result == "Jane Doe"

    def test_contact_without_name(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"email": "anon@example.com"})
        assert result == "(no name) <anon@example.com>"

    def test_unknown_dict_fallback(self) -> None:
        from robotsix_calendar_agent.agent import _summarize_item

        result = _summarize_item({"color": "blue", "size": 3})
        # Should fall through to json.dumps
        assert "color" in result
        assert "blue" in result


# ---------------------------------------------------------------------------
# _render_reply unit tests
# ---------------------------------------------------------------------------


class TestRenderReply:
    def test_deleted_confirmation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("delete_event", {"deleted": True}) == (
            "Done — the item was deleted."
        )

    def test_empty_list_events(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_events", []) == "No events found."

    def test_empty_list_calendars(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_calendars", []) == "No calendars found."

    def test_empty_list_tasks(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_tasks", []) == "No tasks found."

    def test_empty_list_contacts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_contacts", []) == "No contacts found."

    def test_empty_list_unknown_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("frobnicate", []) == "No items found."

    def test_non_empty_list(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_events",
            [
                {"summary": "Lunch", "dtstart": "2026-01-02T12:00:00", "uid": "e1"},
                {"summary": "Dinner", "dtstart": "2026-01-02T19:00:00"},
            ],
        )
        assert result.startswith("Found 2:\n")
        assert "Lunch" in result
        assert "Dinner" in result
        assert "- " in result

    def test_dict_update_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "update_event", {"summary": "Updated meeting", "uid": "e1"}
        )
        assert result.startswith("Updated: ")

    def test_dict_create_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("create_event", {"summary": "New event", "uid": "e2"})
        assert result.startswith("Created: ")

    def test_dict_other_operation(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("delete_event", {"summary": "X"})
        assert result.startswith("Result: ")

    def test_fallback_non_dict_non_list(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        assert _render_reply("list_events", 42) == "42"
        assert _render_reply("list_events", "plain") == "plain"

    def test_list_with_calendar_strings(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply("list_calendars", ["Robotsix", "Birthdays"])
        assert "Found 2" in result
        assert "Robotsix" in result
        assert "Birthdays" in result

    def test_list_with_contact_dicts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_contacts",
            [{"full_name": "John Doe", "email": "j@x.com"}, {"full_name": "Jane"}],
        )
        assert "Found 2" in result
        assert "John Doe" in result
        assert "Jane" in result

    def test_list_with_task_dicts(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        result = _render_reply(
            "list_tasks",
            [
                {
                    "summary": "Buy milk",
                    "due": "2026-06-21",
                    "status": "NEEDS-ACTION",
                    "uid": "t1",
                }
            ],
        )
        assert "Found 1" in result
        assert "Buy milk" in result

    def test_deleted_not_true_is_not_deleted_branch(self) -> None:
        from robotsix_calendar_agent.agent import _render_reply

        # {"deleted": False} should NOT match the deleted branch — falls to dict branch
        result = _render_reply("delete_event", {"deleted": False, "uid": "e1"})
        assert result != "Done — the item was deleted."
        assert "Result:" in result
