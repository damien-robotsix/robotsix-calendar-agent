"""Tests for the long-lived in-process entrypoint."""

from __future__ import annotations

import signal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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
            patch("robotsix_calendar_agent.logging_config.setup_logging"),
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
