"""Tests for IntentParser — llmio model calls mocked."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock robotsix_llmio in sys.modules
# ---------------------------------------------------------------------------

_mock_llmio = MagicMock()
_mock_llmio_core = MagicMock()
sys.modules["robotsix_llmio"] = _mock_llmio
sys.modules["robotsix_llmio.core"] = _mock_llmio_core

from robotsix_calendar_agent.intent_parser import (  # noqa: E402
    CalendarOperation,
    ContactOperation,
    IntentParseError,
    IntentParser,
    ParsedIntent,
    _IntentOutput,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_run_agent(
    operation: str, params: dict[str, Any] | None = None
) -> _IntentOutput:
    """Return a mock intent output."""
    return _IntentOutput(operation=operation, params=params or {})


def _setup_llmio_mock(output: _IntentOutput | Exception) -> MagicMock:
    """Set up llmio mocks: get_provider + run_agent return the given output."""
    mock_provider = MagicMock()
    mock_handle = MagicMock()
    mock_provider.build_agent.return_value = mock_handle
    _mock_llmio_core.get_provider.return_value = mock_provider

    if isinstance(output, Exception):
        _mock_llmio_core.run_agent.side_effect = output
    else:
        _mock_llmio_core.run_agent.return_value = output

    return mock_handle


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParse:
    @pytest.mark.parametrize(
        "instruction,expected_op,expected_params",
        [
            (
                "list events this week",
                CalendarOperation.LIST_EVENTS,
                {"start": "2026-06-15T00:00:00", "end": "2026-06-21T23:59:59"},
            ),
            (
                "add a dentist appointment next Tuesday at 3pm",
                CalendarOperation.CREATE_EVENT,
                {
                    "summary": "dentist appointment",
                    "dtstart": "2026-06-23T15:00:00",
                    "dtend": "2026-06-23T16:00:00",
                },
            ),
            (
                "reschedule the dentist to 4pm",
                CalendarOperation.UPDATE_EVENT,
                {"uid": "", "dtstart": "2026-06-23T16:00:00"},
            ),
            (
                "cancel the dentist appointment",
                CalendarOperation.DELETE_EVENT,
                {"uid": ""},
            ),
            (
                "show all contacts",
                ContactOperation.LIST_CONTACTS,
                {},
            ),
            (
                "add John Doe, john@example.com",
                ContactOperation.CREATE_CONTACT,
                {
                    "full_name": "John Doe",
                    "email": "john@example.com",
                },
            ),
            (
                "change John's email to john.doe@example.com",
                ContactOperation.UPDATE_CONTACT,
                {
                    "uid": "",
                    "email": "john.doe@example.com",
                },
            ),
            (
                "remove John Doe from contacts",
                ContactOperation.DELETE_CONTACT,
                {"uid": ""},
            ),
        ],
    )
    def test_classifies_operation(
        self,
        instruction: str,
        expected_op: CalendarOperation | ContactOperation,
        expected_params: dict[str, Any],
    ) -> None:
        """Verify all 8 operation types are classified correctly."""
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(_mock_run_agent(str(expected_op), expected_params))

        parser = IntentParser()
        result = parser.parse(instruction)

        assert isinstance(result, ParsedIntent)
        assert result.operation == expected_op
        for key, value in expected_params.items():
            assert result.params.get(key) == value
        assert result.original_text == instruction


class TestParseError:
    def test_raises_intent_parse_error_on_llmio_failure(self) -> None:
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(RuntimeError("model unavailable"))

        parser = IntentParser()

        with pytest.raises(IntentParseError, match="Intent parsing failed"):
            parser.parse("list events")

    def test_runs_inner_callback_and_returns_output(self) -> None:
        """run_agent invokes the _run callback, exercising handle.run_sync."""
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        mock_handle = _setup_llmio_mock(_mock_run_agent("list_events", {}))

        # Make run_sync return an object with a .output attribute (pydantic-ai >=1).
        run_result = MagicMock()
        run_result.output = _IntentOutput(operation="list_events", params={})
        mock_handle.run_sync.return_value = run_result

        # Make run_agent actually call the supplied _run callback.
        def _call_run(handle: object, run: object, **kwargs: object) -> object:
            return run()  # type: ignore[operator]

        _mock_llmio_core.run_agent.side_effect = _call_run

        parser = IntentParser()
        result = parser.parse("list events this week")

        mock_handle.run_sync.assert_called_once_with("list events this week")
        assert result.operation == CalendarOperation.LIST_EVENTS

    def test_raises_on_unexpected_output_type(self) -> None:
        """A non-_IntentOutput result raises IntentParseError (re-raised cleanly)."""
        _mock_llmio_core.reset_mock(return_value=True, side_effect=True)
        _setup_llmio_mock(_mock_run_agent("list_events", {}))
        _mock_llmio_core.run_agent.return_value = {"not": "an output"}

        parser = IntentParser()

        with pytest.raises(IntentParseError, match="Unexpected output type"):
            parser.parse("list events")
