"""Tests for logging setup via :func:`robotsix_llmio.logging.setup_logging`."""

from __future__ import annotations

import json
import logging

import pytest
from robotsix_calendar_agent.logging_config import setup_logging

# ---------------------------------------------------------------------------
# setup_logging integration
# ---------------------------------------------------------------------------


def _clear_calendar_agent_logger() -> logging.Logger:
    """Reset the calendar-agent logger so each test starts clean."""
    logger = logging.getLogger("robotsix_calendar_agent")
    logger.handlers.clear()
    logger.propagate = True
    return logger


class TestSetupLogging:
    def test_sets_level(self) -> None:
        logger = _clear_calendar_agent_logger()
        setup_logging(
            level="DEBUG", fmt="console", loggers=("robotsix_calendar_agent",)
        )
        assert logger.level == logging.DEBUG

    def test_json_format_produces_valid_json(self) -> None:
        logger = _clear_calendar_agent_logger()
        setup_logging(level="INFO", fmt="json", loggers=("robotsix_calendar_agent",))
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
        logger = _clear_calendar_agent_logger()
        setup_logging(level="INFO", fmt="console", loggers=("robotsix_calendar_agent",))
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
        logger = _clear_calendar_agent_logger()
        setup_logging(level="INFO", fmt="console", loggers=("robotsix_calendar_agent",))
        count = len(logger.handlers)
        setup_logging(level="DEBUG", fmt="json", loggers=("robotsix_calendar_agent",))
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
