"""Tests for ComponentAgentResponder -- monitor, config-get, config-set."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from robotsix_calendar_agent.component_agent.responder import (
    COMPONENT_KINDS,
    ComponentAgentResponder,
)
from robotsix_calendar_agent.component_agent.settings import ComponentAgentSettings
from robotsix_calendar_agent.settings import Settings
from tests.conftest import (
    _mock_agent_comm_protocol,
    make_request,
    setup_mocks,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides: Any) -> Settings:
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


def _mock_agent() -> MagicMock:
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
        agent = _mock_agent()
        settings = _settings()
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
        agent = _mock_agent()
        settings = _settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "monitor"})
        responder.on_request(req)
        agent.monitor_snapshot.assert_called_once()

    def test_monitor_with_no_agent_returns_error(self) -> None:
        setup_mocks()
        settings = _settings()
        responder = ComponentAgentResponder(None, settings)

        req = make_request({"kind": "monitor"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "internal_error"


class TestResponderConfigGet:
    def test_config_get_returns_snapshot_and_descriptors(self) -> None:
        setup_mocks()
        agent = _mock_agent()
        settings = _settings()
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
        agent = _mock_agent()
        settings = _settings()
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
        agent = _mock_agent()
        settings = _settings()
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
        agent = _mock_agent()
        settings = _settings()
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
        agent = _mock_agent()
        settings = _settings()
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
        agent = _mock_agent()
        settings = _settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-set"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "invalid_request"

    def test_empty_updates_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_agent()
        settings = _settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-set", "updates": {}})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "invalid_request"

    def test_updates_not_dict_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_agent()
        settings = _settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "config-set", "updates": "not-a-dict"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "invalid_request"


class TestResponderUnknownKind:
    def test_unknown_kind_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_agent()
        settings = _settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"kind": "bogus"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unknown_kind"

    def test_missing_kind_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_agent()
        settings = _settings()
        responder = ComponentAgentResponder(agent, settings)

        req = make_request({"not_kind": "x"})
        responder.on_request(req)

        _mock_agent_comm_protocol.Error.to.assert_called()
        _, kwargs = _mock_agent_comm_protocol.Error.to.call_args
        assert kwargs["code"] == "unknown_kind"

    def test_empty_body_returns_error(self) -> None:
        setup_mocks()
        agent = _mock_agent()
        settings = _settings()
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
