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
        "BROKER_HOST",
        "BROKER_PORT",
        "BROKER_TLS_CA",
        "BROKER_CLIENT_CERT",
        "BROKER_CLIENT_KEY",
        "BROKER_AGENT_TOKEN",
    )
    for key in keys:
        os.environ.pop(key, None)
    yield
    for key in keys:
        os.environ.pop(key, None)


def _set_brokered_env() -> None:
    os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
    os.environ["BROKER_HOST"] = "broker.example.com"
    os.environ["BROKER_TLS_CA"] = "/certs/ca.pem"
    os.environ["BROKER_AGENT_TOKEN"] = "secret-token"


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

    def test_brokered_value_builds_broker_client(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        sentinel = MagicMock(name="broker_client")
        _mock_agent_comm_transport.BrokerClient.return_value = sentinel

        transport = brokered_entrypoint._build_transport()

        assert transport is sentinel
        _mock_agent_comm_transport.BrokerClient.assert_called_once()
        _, kwargs = _mock_agent_comm_transport.BrokerClient.call_args
        assert kwargs["host"] == "broker.example.com"
        assert kwargs["port"] == 9090
        assert kwargs["tls_ca"] == "/certs/ca.pem"
        assert kwargs["token"] == "secret-token"

    def test_invalid_value_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "bogus"
        with pytest.raises(ValueError, match="CALENDAR_AGENT_TRANSPORT"):
            brokered_entrypoint._build_transport()

    def test_main_passes_inprocess_transport_to_agent(self) -> None:
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

        _, kwargs = mock_agent_cls.call_args
        assert kwargs["transport"] is None

    def test_main_passes_brokered_transport_to_agent(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        sentinel = MagicMock(name="broker_client")
        _mock_agent_comm_transport.BrokerClient.return_value = sentinel

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

        _, kwargs = mock_agent_cls.call_args
        assert kwargs["transport"] is sentinel


# ---------------------------------------------------------------------------
# Env var validation
# ---------------------------------------------------------------------------


class TestEnvValidation:
    def test_missing_host_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
        os.environ["BROKER_TLS_CA"] = "/certs/ca.pem"
        os.environ["BROKER_AGENT_TOKEN"] = "secret-token"
        with pytest.raises(ValueError, match="BROKER_HOST"):
            brokered_entrypoint._build_transport()

    def test_missing_tls_ca_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
        os.environ["BROKER_HOST"] = "broker.example.com"
        os.environ["BROKER_AGENT_TOKEN"] = "secret-token"
        with pytest.raises(ValueError, match="BROKER_TLS_CA"):
            brokered_entrypoint._build_transport()

    def test_missing_token_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
        os.environ["BROKER_HOST"] = "broker.example.com"
        os.environ["BROKER_TLS_CA"] = "/certs/ca.pem"
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
