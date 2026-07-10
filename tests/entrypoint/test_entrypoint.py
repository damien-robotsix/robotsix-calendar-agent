"""Tests for the long-lived in-process entrypoint."""

from __future__ import annotations

import json
import logging
import signal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _setup_logging integration
# ---------------------------------------------------------------------------


def _clear_calendar_agent_logger() -> logging.Logger:
    """Reset the calendar-agent logger so each test starts clean."""
    logger = logging.getLogger("robotsix_calendar_agent")
    logger.handlers.clear()
    logger.propagate = True
    return logger


class TestSetupLogging:
    def test_sets_level(self) -> None:
        from robotsix_calendar_agent.entrypoint import _setup_logging

        logger = _clear_calendar_agent_logger()
        _setup_logging(
            level="DEBUG", fmt="console", loggers=("robotsix_calendar_agent",)
        )
        assert logger.level == logging.DEBUG

    def test_json_format_produces_valid_json(self) -> None:
        from robotsix_calendar_agent.entrypoint import _setup_logging

        logger = _clear_calendar_agent_logger()
        _setup_logging(level="INFO", fmt="json", loggers=("robotsix_calendar_agent",))
        assert logger.handlers
        handler = logger.handlers[0]

        record = logging.LogRecord(
            name="robotsix_calendar_agent.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        output = handler.format(record)
        obj = json.loads(output)
        assert obj["name"] == "robotsix_calendar_agent.test"
        assert obj["level"] == "INFO"
        assert obj["message"] == "hello world"

    def test_console_format_contains_message(self) -> None:
        from robotsix_calendar_agent.entrypoint import _setup_logging

        logger = _clear_calendar_agent_logger()
        _setup_logging(
            level="INFO", fmt="console", loggers=("robotsix_calendar_agent",)
        )
        assert logger.handlers
        handler = logger.handlers[0]

        record = logging.LogRecord(
            name="robotsix_calendar_agent.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = handler.format(record)
        assert "hello world" in output

    def test_idempotent(self) -> None:
        from robotsix_calendar_agent.entrypoint import _setup_logging

        logger = _clear_calendar_agent_logger()
        _setup_logging(
            level="INFO", fmt="console", loggers=("robotsix_calendar_agent",)
        )
        count = len(logger.handlers)
        _setup_logging(level="DEBUG", fmt="json", loggers=("robotsix_calendar_agent",))
        assert len(logger.handlers) == count


# ---------------------------------------------------------------------------
# Settings LOG_LEVEL validation
# ---------------------------------------------------------------------------


def test_log_level_validation_rejects_invalid() -> None:
    """Setting an invalid LOG_LEVEL must raise ValidationError."""
    from pydantic import ValidationError

    from robotsix_calendar_agent.settings import Settings

    with pytest.raises(ValidationError):
        Settings(LOG_LEVEL="GARBAGE")


def test_log_level_validation_normalises_case() -> None:
    """LOG_LEVEL must be normalised to uppercase."""
    from robotsix_calendar_agent.settings import Settings

    s = Settings(LOG_LEVEL="debug")
    assert s.LOG_LEVEL == "DEBUG"


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_inprocess_builds_calendar_and_blocks(self) -> None:
        from robotsix_calendar_agent import entrypoint

        with (
            patch("robotsix_calendar_agent.entrypoint.CalendarAgent") as mock_cal,
            patch("robotsix_calendar_agent.entrypoint._serve_blocking") as mock_serve,
            patch("robotsix_calendar_agent.settings.Settings"),
            patch("robotsix_calendar_agent.entrypoint._setup_logging"),
        ):
            entrypoint.main()

        _args, _kwargs = mock_cal.call_args
        mock_serve.assert_called_once_with(mock_cal.return_value)


# ---------------------------------------------------------------------------
# _serve_blocking signal handling (in-process mode)
# ---------------------------------------------------------------------------


class TestServeBlocking:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    def test_signal_triggers_stop_and_clean_exit(self, sig: int) -> None:
        from robotsix_calendar_agent import entrypoint

        handlers: dict[int, Any] = {}

        def fake_signal(signum: int, handler: Any) -> None:
            handlers[signum] = handler

        agent = MagicMock(name="calendar")

        with (
            patch(
                "robotsix_calendar_agent.entrypoint.signal.signal",
                fake_signal,
            ),
            patch(
                "robotsix_calendar_agent.entrypoint.threading.Event"
            ) as mock_event_cls,
        ):

            def wait_side_effect(*_a: Any, **_k: Any) -> None:
                handlers[sig](sig, None)

            mock_event = mock_event_cls.return_value
            mock_event.wait.side_effect = wait_side_effect

            entrypoint._serve_blocking(agent)

        mock_event.set.assert_called_once()
        agent.start.assert_called_once()
        agent.stop.assert_called_once()
