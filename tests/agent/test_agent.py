"""Tests for CalendarAgent — all external deps mocked."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from robotsix_calendar_agent.add_to_calendar_handler import (
    ERROR_INVALID_DATES,
    ERROR_MISSING_DATES,
    ERROR_MISSING_SUBJECT,
)

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
    def test_valid_request_creates_event(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
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

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["correlation_id"] == "corr-123"
        assert body["result"]["status"] == "created"
        assert body["result"]["event"]["uid"] == "evt-1"
        assert body["result"]["event"]["summary"] == "Test Subject"
        assert "confirmation_text" in body["result"]
        assert "Test Subject" in body["result"]["confirmation_text"]

        mock_caldav.create_event.assert_called_once()
        calendar_agent._mock_parser.parse.assert_not_called()

    def test_missing_subject_returns_error(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(subject="", correlation_id="corr-1")
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT
        assert body["correlation_id"] == "corr-1"

    def test_missing_dates_returns_error(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(
            suggested_dtstart="", suggested_dtend="", correlation_id="corr-2"
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES
        assert body["correlation_id"] == "corr-2"

    def test_empty_dtstart_returns_missing_dates(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(
            suggested_dtstart="", correlation_id="corr-3"
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES

    def test_invalid_date_string_returns_invalid_dates(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(
            suggested_dtstart="not-a-date", correlation_id="corr-4"
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_dtend_before_dtstart_returns_invalid_dates(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(
            suggested_dtstart="2026-03-15T10:00:00",
            suggested_dtend="2026-03-15T09:00:00",
            correlation_id="corr-5",
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_dtend_equal_to_dtstart_returns_invalid_dates(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(
            suggested_dtstart="2026-03-15T09:00:00",
            suggested_dtend="2026-03-15T09:00:00",
            correlation_id="corr-eq",
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_INVALID_DATES

    def test_operation_error_propagates_code(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        from robotsix_calendar_agent.caldav_client import OperationError

        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.create_event.side_effect = OperationError(
            code="auth_failed", message="Authentication failed"
        )

        req = make_add_to_calendar_request(correlation_id="corr-6")
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == "auth_failed"
        assert body["correlation_id"] == "corr-6"

    def test_unexpected_exception_returns_internal_error(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        mock_caldav = calendar_agent._mock_caldav
        mock_caldav.create_event.side_effect = RuntimeError("boom")

        req = make_add_to_calendar_request(correlation_id="corr-7")
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == "internal_error"
        assert body["correlation_id"] == "corr-7"

    def test_add_to_calendar_bypasses_intent_parser(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        mock_caldav = calendar_agent._mock_caldav
        created_event = MagicMock(
            uid="evt-x",
            summary="S",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        mock_caldav.create_event.return_value = created_event

        req = make_add_to_calendar_request(
            subject="S",
            description="",
            location="",
            correlation_id="c",
        )
        calendar_agent._handle_request(req)

        calendar_agent._mock_parser.parse.assert_not_called()

    def test_correlation_id_echoed_on_success(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        mock_caldav = calendar_agent._mock_caldav
        created_event = MagicMock(
            uid="evt-y",
            summary="S",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        mock_caldav.create_event.return_value = created_event

        req = make_add_to_calendar_request(
            subject="S",
            description="",
            location="",
            correlation_id="my-custom-id",
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["correlation_id"] == "my-custom-id"

    def test_missing_correlation_id_echoes_empty_string(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        mock_caldav = calendar_agent._mock_caldav
        created_event = MagicMock(
            uid="evt-z",
            summary="S",
            description="",
            location="",
            dtstart="2026-03-15T09:00:00",
            dtend="2026-03-15T10:00:00",
            calendar_id="cal",
        )
        mock_caldav.create_event.return_value = created_event

        req = make_add_to_calendar_request(
            subject="S",
            description="",
            location="",
            correlation_id="",
        )
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["correlation_id"] == ""

    def test_whitespace_only_subject_returns_missing_subject(
        self, calendar_agent: MagicMock, make_add_to_calendar_request: MagicMock
    ) -> None:
        req = make_add_to_calendar_request(subject="   ", correlation_id="corr-ws")
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Response.to.call_args
        _, kwargs = call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_MISSING_SUBJECT

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
        calendar_agent._mock_caldav.create_event.assert_called_once()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert body["correlation_id"] == "corr-llm"
        assert body["result"]["status"] == "created"
        assert body["result"]["event"]["uid"] == "evt-llm"

    def test_llm_cannot_resolve_returns_missing_dates(
        self, calendar_agent: MagicMock
    ) -> None:
        mock_parser = calendar_agent._mock_parser
        # Parser returns a non-create_event intent → no usable dates.
        mock_parser.parse.return_value = MagicMock(
            operation="list_events",
            params={},
        )

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
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert body["error"]["code"] == ERROR_MISSING_DATES
        assert body["correlation_id"] == "corr-nodate"


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
