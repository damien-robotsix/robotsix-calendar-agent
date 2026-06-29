"""Tests for :mod:`robotsix_calendar_agent.logging_config`."""

from __future__ import annotations

import json
import logging

import pytest

from robotsix_calendar_agent.logging_config import JsonFormatter, configure_logging

# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------


def test_json_formatter_produces_valid_json() -> None:
    """A formatted record must be parseable JSON with expected keys."""
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    output = fmt.format(record)
    obj = json.loads(output)
    assert obj["name"] == "test.logger"
    assert obj["level"] == "INFO"
    assert obj["message"] == "hello world"
    assert "time" in obj


def test_json_formatter_includes_exc_info() -> None:
    """Exception info must be serialised into the output."""
    fmt = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = None
        import sys

        exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="t",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="fail",
            args=(),
            exc_info=exc_info,
        )
    output = fmt.format(record)
    obj = json.loads(output)
    assert "exc_info" in obj
    assert "ValueError" in obj["exc_info"]


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def test_configure_logging_sets_level() -> None:
    """Calling configure_logging must set the root logger level."""
    import robotsix_calendar_agent.logging_config as lc

    root = logging.getLogger()
    original = root.level
    lc._configured = False
    try:
        configure_logging("DEBUG", json_logs=False)
        assert root.level == logging.DEBUG
    finally:
        root.setLevel(original)
        lc._configured = False


def test_configure_logging_json_logs_adds_handler() -> None:
    """With json_logs=True a handler with JsonFormatter must be added."""
    root = logging.getLogger()
    before = len(root.handlers)
    # configure_logging is idempotent; reset the guard for this test.
    import robotsix_calendar_agent.logging_config as lc

    lc._configured = False
    try:
        configure_logging("WARNING", json_logs=True)
        assert len(root.handlers) == before + 1
        handler = root.handlers[-1]
        assert isinstance(handler.formatter, JsonFormatter)
    finally:
        if len(root.handlers) > before:
            root.removeHandler(root.handlers[-1])
        lc._configured = False


def test_configure_logging_idempotent() -> None:
    """Calling configure_logging twice must not add duplicate handlers."""
    import robotsix_calendar_agent.logging_config as lc

    lc._configured = False
    root = logging.getLogger()
    before = len(root.handlers)
    try:
        configure_logging("INFO", json_logs=False)
        after_first = len(root.handlers)
        configure_logging("DEBUG", json_logs=False)
        assert len(root.handlers) == after_first
    finally:
        if len(root.handlers) > before:
            root.removeHandler(root.handlers[-1])
        lc._configured = False


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
