"""Tests for CalendarAgent — all external deps mocked."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock robotsix_agent_comm in sys.modules before anything imports it
# ---------------------------------------------------------------------------

_mock_agent_comm = MagicMock()
_mock_agent_comm_sdk = MagicMock()
_mock_agent_comm_protocol = MagicMock()
_mock_agent_comm_transport = MagicMock()

sys.modules["robotsix_agent_comm"] = _mock_agent_comm
sys.modules["robotsix_agent_comm.sdk"] = _mock_agent_comm_sdk
sys.modules["robotsix_agent_comm.protocol"] = _mock_agent_comm_protocol
sys.modules["robotsix_agent_comm.transport"] = _mock_agent_comm_transport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_mocks() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Configure the mocked robotsix_agent_comm modules and return key mocks."""
    mock_registry = MagicMock()
    mock_agent = MagicMock()

    _mock_agent_comm_transport.Registry.return_value = mock_registry
    _mock_agent_comm_sdk.Agent.return_value = mock_agent

    # Use MagicMock for Response.to and Error.to so we can inspect call_args
    _mock_response_to = MagicMock(return_value=MagicMock())
    _mock_error_to = MagicMock(return_value=MagicMock())
    _mock_agent_comm_protocol.Response.to = _mock_response_to
    _mock_agent_comm_protocol.Error.to = _mock_error_to

    return mock_registry, mock_agent, _mock_response_to, _mock_error_to


def _make_request(body: dict) -> MagicMock:
    req = MagicMock()
    req.body = body
    return req


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env() -> None:
    """Remove Radicale env vars so tests don't leak state."""
    for key in ("RADICALE_URL", "RADICALE_USERNAME", "RADICALE_PASSWORD"):
        os.environ.pop(key, None)


@pytest.fixture
def calendar_agent() -> object:
    """Create a CalendarAgent with all external deps mocked."""
    _setup_mocks()

    with (
        patch(
            "robotsix_calendar_agent.agent.CalDavClient",
            autospec=True,
        ) as mock_caldav,
        patch(
            "robotsix_calendar_agent.agent.IntentParser",
            autospec=True,
        ) as mock_parser_cls,
    ):
        mock_parser = MagicMock()
        mock_parser_cls.return_value = mock_parser

        os.environ["RADICALE_URL"] = "https://radicale.example.com"
        os.environ["RADICALE_USERNAME"] = "user"
        os.environ["RADICALE_PASSWORD"] = "pass"

        from robotsix_calendar_agent.agent import CalendarAgent

        agent = CalendarAgent()
        agent._mock_parser = mock_parser  # type: ignore[attr-defined]
        agent._mock_caldav = mock_caldav.return_value  # type: ignore[attr-defined]
        agent._mock_agent_comm = _mock_agent_comm_sdk.Agent.return_value  # type: ignore[attr-defined]

        yield agent


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCalendarAgentInit:
    def test_creates_with_env_vars(self) -> None:
        _setup_mocks()

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
        _setup_mocks()

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

        req = _make_request({"instruction": "list events this week"})
        result = calendar_agent._handle_request(req)

        assert result is not None
        _mock_agent_comm_protocol.Response.to.assert_called()

    def test_missing_instruction_returns_error(self, calendar_agent: MagicMock) -> None:
        req = _make_request({"not_instruction": "x"})
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "missing_instruction"

    def test_parse_error_returns_error(self, calendar_agent: MagicMock) -> None:
        from robotsix_calendar_agent.intent_parser import IntentParseError

        mock_parser = calendar_agent._mock_parser
        mock_parser.parse.side_effect = IntentParseError("bad input")

        req = _make_request({"instruction": "gibberish"})
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

        req = _make_request({"instruction": "delete event evt-1"})
        calendar_agent._handle_request(req)

        call_args = _mock_agent_comm_protocol.Error.to.call_args
        _, kwargs = call_args
        assert kwargs.get("code") == "not_found"

    def test_agent_registers_as_calendar(self) -> None:
        _setup_mocks()

        os.environ["RADICALE_URL"] = "https://x.com"
        os.environ["RADICALE_USERNAME"] = "u"
        os.environ["RADICALE_PASSWORD"] = "p"

        with (
            patch("robotsix_calendar_agent.agent.CalDavClient"),
            patch("robotsix_calendar_agent.agent.IntentParser"),
        ):
            from robotsix_calendar_agent.agent import CalendarAgent

            CalendarAgent(agent_id="calendar")

            _mock_agent_comm_sdk.Agent.assert_called_with(
                "calendar", _mock_agent_comm_transport.Registry.return_value
            )
