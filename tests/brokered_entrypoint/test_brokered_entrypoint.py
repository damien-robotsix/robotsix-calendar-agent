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

from robotsix_calendar_agent.brokered_entrypoint import (
    COMPONENT_KINDS,
    ComponentAgentResponder,
)
from robotsix_calendar_agent.component_agent.settings import ComponentAgentSettings
from robotsix_calendar_agent.settings import Settings
from tests.conftest import (
    _mock_agent_comm_protocol,
    _mock_agent_comm_sdk,
    make_request,
    setup_mocks,
)


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
        assert kwargs["broker_port"] == 9090
        assert kwargs["broker_scheme"] == "https"
        assert kwargs["broker_token"] == "secret-token"
        assert kwargs["tls_ca"] is None
        assert kwargs["ssl_context"] is None

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

        with patch(
            "robotsix_calendar_agent.brokered_entrypoint.ssl.SSLContext"
        ) as mock_ssl_ctx_cls:
            brokered_entrypoint._build_brokered_agent()

        args, kwargs = _mock_agent_comm_sdk.BrokeredAgent.call_args
        assert args[0] == "calendar-staging"
        assert kwargs["broker_port"] == 9090
        assert kwargs["broker_scheme"] == "http"
        assert kwargs["tls_ca"] is None  # ssl_context takes precedence
        assert kwargs["ssl_context"] is mock_ssl_ctx_cls.return_value


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
        assert kwargs.get("component_responder") is None
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

        _args, kwargs = mock_cal.call_args
        assert kwargs.get("component_responder") is None
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


# ---------------------------------------------------------------------------
# ComponentAgentResponder — monitor, config-get, config-set
# (merged from tests/component_agent/test_responder.py)
# ---------------------------------------------------------------------------


def _responder_settings(**overrides: Any) -> Settings:
    """Build a Settings object with test-friendly defaults."""
    env = {
        "RADICALE_URL": "https://rad.example.com",
        "RADICALE_USERNAME": "user",
        "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
        "RADICALE_DEFAULT_CALENDAR": "TestCal",
    }
    env.update(overrides)
    with patch.dict(os.environ, env, clear=True):
        return Settings()


def _mock_responder_agent() -> MagicMock:
    """Build a mock CalendarAgent with telemetry and a fake caldav client."""
    agent = MagicMock()
    agent.monitor_snapshot.return_value = {
        "agent_id": "test-calendar",
        "uptime_seconds": 12.345,
        "request_count": 7,
        "error_count": 1,
        "in_flight": 0,
        "last_request_ts": 999.0,
        "caldav_url": "https://rad.example.com",
        "default_calendar": "TestCal",
        "caldav_health": {"connected": True, "calendar_count": 3},
    }
    agent._caldav = MagicMock()
    agent._caldav._default_calendar = "TestCal"
    return agent


# ---------------------------------------------------------------------------
# ComponentAgentSettings
# ---------------------------------------------------------------------------


class TestComponentAgentSettings:
    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = ComponentAgentSettings()
            assert s.COMPONENT_AGENT_ENABLED is False

    def test_token_required_when_enabled_raises(self) -> None:
        env = {"COMPONENT_AGENT_ENABLED": "true", "COMPONENT_AGENT_TOKEN": ""}
        with (
            patch.dict(os.environ, env, clear=True),
            pytest.raises(ValueError, match="COMPONENT_AGENT_TOKEN"),
        ):
            ComponentAgentSettings()

    def test_enabled_with_token_passes(self) -> None:
        env = {
            "COMPONENT_AGENT_ENABLED": "true",
            "COMPONENT_AGENT_TOKEN": "secret-token",
        }
        with patch.dict(os.environ, env, clear=True):
            s = ComponentAgentSettings()
            assert s.COMPONENT_AGENT_ENABLED is True
            assert s.COMPONENT_AGENT_TOKEN.get_secret_value() == "secret-token"


# ---------------------------------------------------------------------------
# COMPONENT_KINDS
# ---------------------------------------------------------------------------


class TestComponentKinds:
    def test_kinds_tuple(self) -> None:
        assert set(COMPONENT_KINDS) == {"monitor", "config-get", "config-set"}


# ---------------------------------------------------------------------------
# ComponentAgentResponder
# ---------------------------------------------------------------------------


class TestResponderMonitor:
    def test_monitor_returns_live_telemetry(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "monitor"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Response.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert body["agent_id"] == "test-calendar"
        assert body["uptime_seconds"] == 12.345
        assert body["request_count"] == 7
        assert body["error_count"] == 1
        assert body["caldav_health"]["connected"] is True
        assert body["caldav_health"]["calendar_count"] == 3
        assert "capabilities" in body
        assert set(body["capabilities"]) == set(COMPONENT_KINDS)

    def test_monitor_calls_agent_monitor_snapshot(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "monitor"})
        responder.on_request(req)
        agent.monitor_snapshot.assert_called_once()

    def test_monitor_with_no_agent_returns_error(self) -> None:
        setup_mocks()
        settings = _responder_settings()
        responder = ComponentAgentResponder(None, settings)

        req = make_request({"kind": "monitor"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "internal_error"


class TestResponderConfigGet:
    def test_config_get_returns_snapshot_and_descriptors(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-get"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Response.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert "snapshot" in body
        assert "descriptors" in body
        # secrets redacted
        assert body["snapshot"]["radicale_password"] == "***"

    def test_config_get_secrets_never_leak(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-get"})
        responder.on_request(req)

        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        snapshot = kwargs["body"]["snapshot"]
        for val in snapshot.values():
            if isinstance(val, str):
                assert val != "secret"


class TestResponderConfigSet:
    def test_valid_update_applies_and_returns_audit(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request(
            {
                "kind": "config-set",
                "updates": {"radicale_default_calendar": "NewCal"},
            }
        )
        responder.on_request(req)

        _mock_agent_comm_protocol.Response.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Response.to.call_args
        body = kwargs["body"]
        assert "audit" in body
        assert body["audit"]["radicale_default_calendar"] == ("TestCal", "NewCal")
        assert settings.RADICALE_DEFAULT_CALENDAR == "NewCal"
        # caldav default calendar updated
        assert agent._caldav._default_calendar == "NewCal"

    def test_invalid_key_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request(
            {
                "kind": "config-set",
                "updates": {"radicale_url": "https://evil.com"},
            }
        )
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "not_settable"
        # No mutation occurred
        assert settings.RADICALE_URL == "https://rad.example.com"

    def test_unknown_key_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request(
            {
                "kind": "config-set",
                "updates": {"nonexistent": "val"},
            }
        )
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unknown_key"

    def test_missing_updates_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-set"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "invalid_request"

    def test_empty_updates_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-set", "updates": {}})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "invalid_request"

    def test_updates_not_dict_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-set", "updates": "not-a-dict"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "invalid_request"


class TestResponderUnknownKind:
    def test_unknown_kind_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "bogus"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unknown_kind"

    def test_missing_kind_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"not_kind": "x"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unknown_kind"

    def test_empty_body_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_responder_agent()
        settings = _responder_settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request(None)
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unknown_kind"


# ---------------------------------------------------------------------------
# Responder stays inert when disabled (responder not created)
# ---------------------------------------------------------------------------


class TestResponderInertWhenDisabled:
    def test_responder_not_created_when_disabled(self) -> None:
        """Verify the entrypoint does not build a responder when
        COMPONENT_AGENT_ENABLED is false (the default)."""
        from robotsix_calendar_agent import brokered_entrypoint

        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            result = brokered_entrypoint._build_component_responder(s)
            assert result is None

    def test_responder_not_created_when_sdk_missing(self) -> None:
        """When the SDK is absent, the responder must be None."""
        from robotsix_calendar_agent import brokered_entrypoint

        env = {"COMPONENT_AGENT_ENABLED": "true", "COMPONENT_AGENT_TOKEN": "t"}
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.importlib.util.find_spec",
                return_value=None,
            ),
        ):
            s = Settings()
            result = brokered_entrypoint._build_component_responder(s)
            assert result is None

    def test_responder_created_when_enabled_with_token(self) -> None:
        """When COMPONENT_AGENT_ENABLED=true and a token is set,
        _build_component_responder returns a ComponentAgentResponder."""
        from robotsix_calendar_agent import brokered_entrypoint

        env = {
            "RADICALE_URL": "https://rad.example.com",
            "RADICALE_USERNAME": "user",
            "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
            "COMPONENT_AGENT_ENABLED": "true",
            "COMPONENT_AGENT_TOKEN": "secret-token",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "robotsix_calendar_agent.brokered_entrypoint.importlib.util.find_spec",
                return_value=MagicMock(),
            ),
        ):
            s = Settings()
            result = brokered_entrypoint._build_component_responder(s)
            assert isinstance(result, ComponentAgentResponder)
            assert result._settings is s
