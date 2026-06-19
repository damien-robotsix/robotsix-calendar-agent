"""Tests for the long-lived brokered service entrypoint.

These rely on the ``robotsix_agent_comm`` submodule mocks installed in
``sys.modules`` by ``conftest.py`` — no real broker, TLS handshake, or
network access is involved.
"""

from __future__ import annotations

import os
import signal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import _mock_agent_comm_transport


@pytest.fixture(autouse=True)
def clean_broker_env() -> Any:
    """Remove transport/broker env vars so tests don't leak state."""
    keys = (
        "CALENDAR_AGENT_TRANSPORT",
        "CALENDAR_AGENT_ID",
        "BROKER_HOST",
        "BROKER_PORT",
        "BROKER_SCHEME",
        "BROKER_TLS_CA",
        "BROKER_AGENT_TOKEN",
    )
    for key in keys:
        os.environ.pop(key, None)
    _mock_agent_comm_transport.create_transport_pair.reset_mock(return_value=True)
    yield
    for key in keys:
        os.environ.pop(key, None)


def _set_brokered_env() -> None:
    os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
    os.environ["BROKER_HOST"] = "broker.example.com"
    os.environ["BROKER_AGENT_TOKEN"] = "secret-token"


def _stub_transport_pair() -> tuple[MagicMock, MagicMock]:
    """Make ``create_transport_pair`` return a ``(registry, transport)`` pair."""
    registry = MagicMock(name="registry")
    transport = MagicMock(name="transport")
    _mock_agent_comm_transport.create_transport_pair.return_value = (
        registry,
        transport,
    )
    return registry, transport


# ---------------------------------------------------------------------------
# Transport selection
# ---------------------------------------------------------------------------


class TestTransportSelection:
    def test_unset_selects_inprocess(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        assert brokered_entrypoint._build_transport() is None

    def test_inprocess_value_selects_inprocess(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "inprocess"
        assert brokered_entrypoint._build_transport() is None

    def test_brokered_value_builds_transport_pair(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        registry, transport = _stub_transport_pair()

        result = brokered_entrypoint._build_transport()

        assert result == (registry, transport)
        _mock_agent_comm_transport.create_transport_pair.assert_called_once()
        args, kwargs = _mock_agent_comm_transport.create_transport_pair.call_args
        assert args == ("brokered",)
        assert kwargs["broker_host"] == "broker.example.com"
        assert kwargs["broker_port"] == 443  # default
        assert kwargs["broker_scheme"] == "https"  # default
        assert kwargs["broker_token"] == "secret-token"
        # System trust by default — no custom CA context.
        assert kwargs["broker_ssl_context"] is None

    def test_brokered_honours_port_and_scheme_overrides(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        os.environ["BROKER_PORT"] = "9090"
        os.environ["BROKER_SCHEME"] = "http"
        _stub_transport_pair()

        brokered_entrypoint._build_transport()

        _, kwargs = _mock_agent_comm_transport.create_transport_pair.call_args
        assert kwargs["broker_port"] == 9090
        assert kwargs["broker_scheme"] == "http"

    def test_invalid_value_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "bogus"
        with pytest.raises(ValueError, match="CALENDAR_AGENT_TRANSPORT"):
            brokered_entrypoint._build_transport()

    def test_main_inprocess_builds_default_agent(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        with (
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.CalendarAgent"
            ) as mock_agent_cls,
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.threading.Event"
            ) as mock_event_cls,
            patch("robotsix_calendar_agent.brokered_entrypoint.signal.signal"),
        ):
            mock_event_cls.return_value.wait.return_value = None
            brokered_entrypoint.main()

        # In-process path: no registry/transport/pull wiring.
        args, kwargs = mock_agent_cls.call_args
        assert args == ()
        assert kwargs == {}

    def test_main_brokered_wires_pull_agent(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        registry, transport = _stub_transport_pair()

        with (
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.CalendarAgent"
            ) as mock_agent_cls,
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.threading.Event"
            ) as mock_event_cls,
            patch("robotsix_calendar_agent.brokered_entrypoint.signal.signal"),
        ):
            mock_event_cls.return_value.wait.return_value = None
            brokered_entrypoint.main()

        args, kwargs = mock_agent_cls.call_args
        assert args == ("robotsix-calendar",)  # default agent id
        assert kwargs["registry"] is registry
        assert kwargs["transport"] is transport
        assert kwargs["pull"] is True

    def test_main_brokered_honours_agent_id_override(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        os.environ["CALENDAR_AGENT_ID"] = "calendar-staging"
        _stub_transport_pair()

        with (
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.CalendarAgent"
            ) as mock_agent_cls,
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.threading.Event"
            ) as mock_event_cls,
            patch("robotsix_calendar_agent.brokered_entrypoint.signal.signal"),
        ):
            mock_event_cls.return_value.wait.return_value = None
            brokered_entrypoint.main()

        args, _ = mock_agent_cls.call_args
        assert args == ("calendar-staging",)


# ---------------------------------------------------------------------------
# Env var validation
# ---------------------------------------------------------------------------


class TestEnvValidation:
    def test_missing_host_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
        os.environ["BROKER_AGENT_TOKEN"] = "secret-token"
        with pytest.raises(ValueError, match="BROKER_HOST"):
            brokered_entrypoint._build_transport()

    def test_missing_token_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
        os.environ["BROKER_HOST"] = "broker.example.com"
        with pytest.raises(ValueError, match="BROKER_AGENT_TOKEN"):
            brokered_entrypoint._build_transport()


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


class TestSignalHandling:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    def test_signal_triggers_stop_and_clean_exit(self, sig: int) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        handlers: dict[int, Any] = {}

        def fake_signal(signum: int, handler: Any) -> None:
            handlers[signum] = handler

        agent = MagicMock(name="agent")

        with (
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.CalendarAgent",
                return_value=agent,
            ),
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.signal.signal",
                fake_signal,
            ),
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.threading.Event"
            ) as mock_event_cls,
        ):
            # Simulate the signal arriving while the entrypoint blocks on wait().
            def wait_side_effect(*_a: Any, **_k: Any) -> None:
                handlers[sig](sig, None)

            mock_event = mock_event_cls.return_value
            mock_event.wait.side_effect = wait_side_effect

            brokered_entrypoint.main()

        # Handler set the stop event and the agent was stopped cleanly.
        mock_event.set.assert_called_once()
        agent.start.assert_called_once()
        agent.stop.assert_called_once()
