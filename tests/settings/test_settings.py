"""Unit tests for the Settings class and its validators."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from robotsix_calendar_agent.settings import Settings

# ---------------------------------------------------------------------------
# _normalize_log_level
# ---------------------------------------------------------------------------


class TestNormalizeLogLevel:
    """Tests for the ``_normalize_log_level`` field validator."""

    def test_strips_whitespace(self) -> None:
        assert Settings._normalize_log_level("  debug  ") == "DEBUG"

    def test_lower_cases(self) -> None:
        assert Settings._normalize_log_level("info") == "INFO"

    def test_mixed_case_and_whitespace(self) -> None:
        assert Settings._normalize_log_level("  Warning  ") == "WARNING"

    def test_already_normalized(self) -> None:
        assert Settings._normalize_log_level("ERROR") == "ERROR"

    def test_invalid_level_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid LOG_LEVEL"):
            Settings._normalize_log_level("BOGUS")


# ---------------------------------------------------------------------------
# Full Settings construction with env var overrides
# ---------------------------------------------------------------------------


class TestSettingsConstruction:
    """Integration-style tests exercising ``Settings()`` with env vars."""

    def test_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.RADICALE_URL == ""
            assert s.RADICALE_USERNAME == ""
            assert s.RADICALE_PASSWORD.get_secret_value() == ""
            assert s.RADICALE_DEFAULT_CALENDAR == "Robotsix"
            assert s.LOG_LEVEL == "INFO"
            assert s.JSON_LOGS is False

    def test_radicale_fields_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RADICALE_URL": "https://radicale.example.com",
                "RADICALE_USERNAME": "user",
                "RADICALE_PASSWORD": "secret",  # pragma: allowlist secret
            },
            clear=True,
        ):
            s = Settings()
            assert s.RADICALE_URL == "https://radicale.example.com"
            assert s.RADICALE_USERNAME == "user"
            assert s.RADICALE_PASSWORD.get_secret_value() == "secret"

    def test_radicale_default_calendar_from_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RADICALE_URL": "https://x.com",
                "RADICALE_USERNAME": "u",
                "RADICALE_PASSWORD": "p",  # pragma: allowlist secret
                "RADICALE_DEFAULT_CALENDAR": "Damien",
            },
            clear=True,
        ):
            s = Settings()
            assert s.RADICALE_DEFAULT_CALENDAR == "Damien"

    def test_radicale_default_calendar_defaults_to_robotsix(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.RADICALE_DEFAULT_CALENDAR == "Robotsix"

    def test_log_level_from_env(self) -> None:
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True):
            s = Settings()
            assert s.LOG_LEVEL == "DEBUG"

    def test_json_logs_from_env(self) -> None:
        with patch.dict(os.environ, {"JSON_LOGS": "true"}, clear=True):
            s = Settings()
            assert s.JSON_LOGS is True

    def test_invalid_log_level_raises_during_construction(self) -> None:
        with (
            patch.dict(os.environ, {"LOG_LEVEL": "BOGUS"}, clear=True),
            pytest.raises(ValueError),
        ):
            Settings()

    def test_ignores_unknown_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RADICALE_URL": "https://x.com",
                "RADICALE_USERNAME": "u",
                "RADICALE_PASSWORD": "p",
                "UNKNOWN_VAR": "ignored",
            },
            clear=True,
        ):
            s = Settings()
            assert s.RADICALE_URL == "https://x.com"
            # extra="ignore" means unknown vars don't cause errors
