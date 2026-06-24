"""Shared pytest fixtures and helpers for CalendarAgent tests."""

from __future__ import annotations

import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Re-export the session-scoped integration fixture so it is explicitly
# available to all test modules.
from tests.caldav_client.caldav_test_server import caldav_client  # noqa: F401

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


def setup_mocks() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Configure the mocked robotsix_agent_comm modules and return key mocks."""
    mock_registry = MagicMock()
    mock_agent = MagicMock()

    _mock_agent_comm_transport.Registry.return_value = mock_registry
    _mock_agent_comm_sdk.Agent.return_value = mock_agent

    # Use MagicMock for Response.to and Error.to so we can inspect call_args
    mock_response_to = MagicMock(return_value=MagicMock())
    mock_error_to = MagicMock(return_value=MagicMock())
    # Make the returned Error mock duck-type as an Error for telemetry
    mock_error_to.return_value.type = MagicMock()
    mock_error_to.return_value.type.name = "ERROR"
    # Make the returned Response mock duck-type as a Response
    mock_response_to.return_value.type = MagicMock()
    mock_response_to.return_value.type.name = "RESPONSE"
    _mock_agent_comm_protocol.Response.to = mock_response_to
    _mock_agent_comm_protocol.Error.to = mock_error_to

    return mock_registry, mock_agent, mock_response_to, mock_error_to


def make_request(body: dict[str, Any] | None) -> MagicMock:
    """Create a mock request carrying the given *body* dict."""
    req = MagicMock()
    req.body = body
    return req


def caldav_event(uid: str = "evt-1") -> MagicMock:
    """Create a mock CalendarEvent with default fields."""
    return MagicMock(
        uid=uid,
        summary="S",
        description="D",
        location="L",
        dtstart="2026-01-02",
        dtend="2026-01-02",
        calendar_id="cal",
    )


def caldav_contact(uid: str = "cnt-1") -> MagicMock:
    """Create a mock Contact with default fields."""
    return MagicMock(
        uid=uid,
        full_name="John Doe",
        email="j@example.com",
        phone="123",
        address="addr",
        addressbook_id="ab",
    )


def caldav_task(uid: str = "task-1") -> MagicMock:
    """Create a mock Task with default fields."""
    return MagicMock(
        uid=uid,
        summary="Buy milk",
        description="Get 2%",
        dtstart="2026-06-20T08:00:00",
        due="2026-06-21",
        status="NEEDS-ACTION",
        calendar_id="cal",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_env() -> None:
    """Remove Radicale env vars so tests don't leak state."""
    for key in ("RADICALE_URL", "RADICALE_USERNAME", "RADICALE_PASSWORD"):
        os.environ.pop(key, None)


@pytest.fixture
def calendar_agent() -> Any:
    """Create a CalendarAgent with all external deps mocked.

    The returned agent has ``_mock_parser``, ``_mock_caldav``, and
    ``_mock_agent_comm`` attributes attached for test assertions.
    """
    setup_mocks()

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
        os.environ["RADICALE_PASSWORD"] = "pass"  # pragma: allowlist secret

        from robotsix_calendar_agent.agent import CalendarAgent

        agent = CalendarAgent()
        agent._mock_parser = mock_parser  # type: ignore[attr-defined]
        agent._mock_caldav = mock_caldav.return_value  # type: ignore[attr-defined]
        agent._mock_agent_comm = _mock_agent_comm_sdk.Agent.return_value  # type: ignore[attr-defined]

        yield agent


@pytest.fixture
def make_add_to_calendar_request() -> Any:
    """Return a factory for add-to-calendar request payloads.

    Usage::

        req = make_add_to_calendar_request(subject="Lunch", correlation_id="c1")
        calendar_agent._handle_request(req)
    """
    from robotsix_calendar_agent.add_to_calendar_handler import (
        ERROR_INVALID_DATES,
        ERROR_MISSING_DATES,
        ERROR_MISSING_SUBJECT,
    )

    def _build(
        *,
        subject: str = "Test Subject",
        body_text: str = "Some body text",
        suggested_dtstart: str = "2026-03-15T09:00:00",
        suggested_dtend: str = "2026-03-15T10:00:00",
        description: str = "Test Description",
        location: str = "Office",
        correlation_id: str = "corr-123",
    ) -> MagicMock:
        payload: dict[str, Any] = {
            "subject": subject,
            "body_text": body_text,
            "suggested_dtstart": suggested_dtstart,
            "suggested_dtend": suggested_dtend,
            "description": description,
            "location": location,
            "correlation_id": correlation_id,
        }
        return make_request({"add_to_calendar": payload})

    # Attach error-code constants so tests can reference them easily.
    _build.ERROR_MISSING_SUBJECT = ERROR_MISSING_SUBJECT  # type: ignore[attr-defined]
    _build.ERROR_MISSING_DATES = ERROR_MISSING_DATES  # type: ignore[attr-defined]
    _build.ERROR_INVALID_DATES = ERROR_INVALID_DATES  # type: ignore[attr-defined]

    return _build
