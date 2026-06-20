"""Tests for the long-lived brokered service entrypoint.

These rely on the ``robotsix_agent_comm`` submodule mocks installed in
``sys.modules`` by ``conftest.py`` — no real broker, TLS handshake, or
network access is involved. The entrypoint now wires the calendar agent onto
the shared :class:`robotsix_agent_comm.sdk.BrokeredAgent`.
"""

from __future__ import annotations

import os
import signal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import _mock_agent_comm_sdk


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
        "BROKER_CLIENT_CERT",
        "BROKER_CLIENT_KEY",
    )
    for key in keys:
        os.environ.pop(key, None)
    _mock_agent_comm_sdk.BrokeredAgent.reset_mock(return_value=True)
    yield
    for key in keys:
        os.environ.pop(key, None)


def _set_brokered_env() -> None:
    os.environ["CALENDAR_AGENT_TRANSPORT"] = "brokered"
    os.environ["BROKER_HOST"] = "broker.example.com"
    os.environ["BROKER_AGENT_TOKEN"] = "secret-token"


def _stub_brokered_agent() -> MagicMock:
    inst = MagicMock(name="brokered_agent")
    inst.agent_id = "robotsix-calendar"
    _mock_agent_comm_sdk.BrokeredAgent.return_value = inst
    return inst


# ---------------------------------------------------------------------------
# _build_brokered_agent
# ---------------------------------------------------------------------------


class TestBuildBrokeredAgent:
    def test_builds_with_defaults(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        _stub_brokered_agent()

        brokered_entrypoint._build_brokered_agent()

        _mock_agent_comm_sdk.BrokeredAgent.assert_called_once()
        args, kwargs = _mock_agent_comm_sdk.BrokeredAgent.call_args
        assert args[0] == "robotsix-calendar"  # default agent id
        assert kwargs["broker_host"] == "broker.example.com"
        assert kwargs["broker_port"] == 443
        assert kwargs["broker_scheme"] == "https"
        assert kwargs["broker_token"] == "secret-token"
        assert kwargs["tls_ca"] is None
        assert kwargs["client_cert"] is None
        assert kwargs["client_key"] is None

    def test_honours_overrides(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        os.environ["BROKER_PORT"] = "9090"
        os.environ["BROKER_SCHEME"] = "http"
        os.environ["CALENDAR_AGENT_ID"] = "calendar-staging"
        os.environ["BROKER_TLS_CA"] = "/certs/ca.pem"
        os.environ["BROKER_CLIENT_CERT"] = "/certs/client.pem"
        os.environ["BROKER_CLIENT_KEY"] = "/certs/client.key"
        _stub_brokered_agent()

        brokered_entrypoint._build_brokered_agent()

        args, kwargs = _mock_agent_comm_sdk.BrokeredAgent.call_args
        assert args[0] == "calendar-staging"
        assert kwargs["broker_port"] == 9090
        assert kwargs["broker_scheme"] == "http"
        assert kwargs["tls_ca"] == "/certs/ca.pem"
        assert kwargs["client_cert"] == "/certs/client.pem"
        assert kwargs["client_key"] == "/certs/client.key"


class TestEnvValidation:
    def test_missing_host_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["BROKER_AGENT_TOKEN"] = "secret-token"
        with pytest.raises(ValueError, match="BROKER_HOST"):
            brokered_entrypoint._build_brokered_agent()

    def test_missing_token_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["BROKER_HOST"] = "broker.example.com"
        with pytest.raises(ValueError, match="BROKER_AGENT_TOKEN"):
            brokered_entrypoint._build_brokered_agent()


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_brokered_wires_calendar_and_serves(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        _set_brokered_env()
        inst = _stub_brokered_agent()

        with patch(
            "robotsix_calendar_agent.brokered_entrypoint.CalendarAgent"
        ) as mock_cal:
            brokered_entrypoint.main()

        # CalendarAgent wires its handler onto the shared brokered client.
        args, kwargs = mock_cal.call_args
        assert args[0] == "robotsix-calendar"
        assert kwargs["agent"] is inst
        # serve_forever() runs the blocking loop.
        inst.serve_forever.assert_called_once()

    def test_inprocess_builds_calendar_and_blocks(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        with (
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.CalendarAgent"
            ) as mock_cal,
            patch(
                "robotsix_calendar_agent.brokered_entrypoint._serve_blocking"
            ) as mock_serve,
        ):
            brokered_entrypoint.main()

        mock_cal.assert_called_once_with()
        mock_serve.assert_called_once_with(mock_cal.return_value)
        _mock_agent_comm_sdk.BrokeredAgent.assert_not_called()

    def test_invalid_mode_raises(self) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        os.environ["CALENDAR_AGENT_TRANSPORT"] = "bogus"
        with pytest.raises(ValueError, match="CALENDAR_AGENT_TRANSPORT"):
            brokered_entrypoint.main()


# ---------------------------------------------------------------------------
# _serve_blocking signal handling (in-process mode)
# ---------------------------------------------------------------------------


class TestServeBlocking:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    def test_signal_triggers_stop_and_clean_exit(self, sig: int) -> None:
        from robotsix_calendar_agent import brokered_entrypoint

        handlers: dict[int, Any] = {}

        def fake_signal(signum: int, handler: Any) -> None:
            handlers[signum] = handler

        agent = MagicMock(name="calendar")

        with (
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.signal.signal",
                fake_signal,
            ),
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.threading.Event"
            ) as mock_event_cls,
        ):

            def wait_side_effect(*_a: Any, **_k: Any) -> None:
                handlers[sig](sig, None)

            mock_event = mock_event_cls.return_value
            mock_event.wait.side_effect = wait_side_effect

            brokered_entrypoint._serve_blocking(agent)

        mock_event.set.assert_called_once()
        agent.start.assert_called_once()
        agent.stop.assert_called_once()
