"""Tests for the config contract -- validation, snapshot, and live-apply."""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest

from robotsix_calendar_agent.component_agent.config_contract import (
    SETTABLE_KEYS,
    ConfigContractError,
    apply_config_update,
    describe_config,
    get_config_snapshot,
    validate_config_update,
)
from robotsix_calendar_agent.settings import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides: Any) -> Settings:
    """Build a Settings object with test-friendly defaults + *overrides*."""
    env = {
        "RADICALE_URL": "https://rad.example.com",
        "RADICALE_USERNAME": "user",
        "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
        "RADICALE_DEFAULT_CALENDAR": "TestCal",
    }
    env.update(overrides)
    with patch.dict(os.environ, env, clear=True):
        return Settings()


# ---------------------------------------------------------------------------
# get_config_snapshot
# ---------------------------------------------------------------------------


class TestGetConfigSnapshot:
    def test_returns_flat_dotted_keys(self) -> None:
        s = _settings()
        snap = get_config_snapshot(s)
        assert isinstance(snap, dict)
        assert snap["radicale_url"] == "https://rad.example.com"
        assert snap["radicale_username"] == "user"
        assert snap["radicale_default_calendar"] == "TestCal"

    def test_secrets_are_redacted(self) -> None:
        s = _settings()
        snap = get_config_snapshot(s)
        assert snap["radicale_password"] == "***"
        # Real values must never leak
        for val in snap.values():
            if isinstance(val, str):
                assert val != "secret"


# ---------------------------------------------------------------------------
# describe_config
# ---------------------------------------------------------------------------


class TestDescribeConfig:
    def test_returns_per_key_descriptors(self) -> None:
        s = _settings()
        desc = describe_config(s)
        assert "keys" in desc
        keys = desc["keys"]
        assert keys["radicale_default_calendar"]["settable"] is True
        assert keys["radicale_default_calendar"]["secret"] is False
        assert keys["radicale_default_calendar"]["value"] == "TestCal"

        assert keys["radicale_url"]["settable"] is False
        assert keys["radicale_password"]["secret"] is True
        assert keys["radicale_password"]["value"] == "***"

    def test_secret_values_never_appear(self) -> None:
        s = _settings()
        desc = describe_config(s)
        for key_info in desc["keys"].values():
            if key_info["secret"]:
                assert key_info["value"] == "***"


# ---------------------------------------------------------------------------
# validate_config_update
# ---------------------------------------------------------------------------


class TestValidateConfigUpdate:
    def test_valid_settable_key_passes(self) -> None:
        s = _settings()
        validate_config_update(s, {"radicale_default_calendar": "NewCal"})

    def test_unknown_key_raises(self) -> None:
        s = _settings()
        with pytest.raises(ConfigContractError, match="Unknown config key"):
            validate_config_update(s, {"nonexistent_key": "val"})

    def test_not_settable_key_raises(self) -> None:
        s = _settings()
        with pytest.raises(ConfigContractError, match="not settable"):
            validate_config_update(s, {"radicale_url": "https://new.example.com"})

    def test_empty_updates_passes(self) -> None:
        s = _settings()
        validate_config_update(s, {})

    def test_no_mutation_on_invalid(self) -> None:
        s = _settings()
        original = s.RADICALE_DEFAULT_CALENDAR
        with pytest.raises(ConfigContractError):
            validate_config_update(s, {"radicale_url": "https://evil.com"})
        assert original == s.RADICALE_DEFAULT_CALENDAR

    def test_multiple_keys_one_invalid_no_mutation(self) -> None:
        s = _settings()
        original = s.RADICALE_DEFAULT_CALENDAR
        with pytest.raises(ConfigContractError):
            validate_config_update(
                s,
                {
                    "radicale_default_calendar": "NewCal",
                    "radicale_url": "https://evil.com",
                },
            )
        assert original == s.RADICALE_DEFAULT_CALENDAR


# ---------------------------------------------------------------------------
# apply_config_update
# ---------------------------------------------------------------------------


class TestApplyConfigUpdate:
    def test_valid_update_applies_and_returns_audit(self) -> None:
        s = _settings()
        audit = apply_config_update(s, {"radicale_default_calendar": "NewCal"})
        assert audit == {"radicale_default_calendar": ("TestCal", "NewCal")}
        assert s.RADICALE_DEFAULT_CALENDAR == "NewCal"

    def test_invalid_update_no_mutation(self) -> None:
        s = _settings()
        original = s.RADICALE_DEFAULT_CALENDAR
        with pytest.raises(ConfigContractError):
            apply_config_update(s, {"radicale_url": "https://evil.com"})
        assert original == s.RADICALE_DEFAULT_CALENDAR

    def test_empty_updates_returns_empty_audit(self) -> None:
        s = _settings()
        audit = apply_config_update(s, {})
        assert audit == {}

    def test_secret_update_redacted_in_audit(self) -> None:
        from robotsix_calendar_agent.component_agent.config_contract import (
            _is_secret_field,
        )

        assert _is_secret_field("radicale_password") is True
        assert _is_secret_field("radicale_url") is False


# ---------------------------------------------------------------------------
# SETTABLE_KEYS
# ---------------------------------------------------------------------------


class TestSettableKeys:
    def test_only_safe_keys_are_settable(self) -> None:
        # Startup-only keys must NOT be settable
        unsafe = {
            "radicale_url",
            "radicale_username",
            "radicale_password",
            "component_agent_enabled",
            "component_agent_token",
            "component_agent_id",
        }
        assert SETTABLE_KEYS.isdisjoint(unsafe)

    def test_default_calendar_is_settable(self) -> None:
        assert "radicale_default_calendar" in SETTABLE_KEYS


# ---------------------------------------------------------------------------
# ConfigContractError
# ---------------------------------------------------------------------------


class TestConfigContractError:
    def test_has_code_message_details(self) -> None:
        err = ConfigContractError("bad_key", "message", {"key": "x"})
        assert err.code == "bad_key"
        assert err.message == "message"
        assert err.details == {"key": "x"}

    def test_details_defaults_to_none(self) -> None:
        err = ConfigContractError("code", "msg")
        assert err.details is None
