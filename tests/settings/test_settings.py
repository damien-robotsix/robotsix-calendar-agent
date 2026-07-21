"""Unit tests for the Settings model and its validators."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

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
# Full Settings construction (plain BaseModel, no env vars)
# ---------------------------------------------------------------------------


class TestSettingsConstruction:
    """Tests exercising ``Settings()`` direct construction."""

    def test_required_fields(self) -> None:
        s = Settings(
            RADICALE_URL="https://radicale.example.com",
            RADICALE_USERNAME="user",
            RADICALE_PASSWORD=SecretStr("secret"),
        )
        assert s.RADICALE_URL == "https://radicale.example.com"
        assert s.RADICALE_USERNAME == "user"
        assert s.RADICALE_PASSWORD.get_secret_value() == "secret"

    def test_defaults(self) -> None:
        s = Settings(
            RADICALE_URL="https://radicale.example.com",
            RADICALE_USERNAME="user",
            RADICALE_PASSWORD=SecretStr("secret"),
        )
        assert s.RADICALE_DEFAULT_CALENDAR == "Robotsix"
        assert s.LOG_LEVEL == "INFO"
        assert s.JSON_LOGS is False
        assert s.CALDAV_TIMEOUT == 30

    def test_override_defaults(self) -> None:
        s = Settings(
            RADICALE_URL="https://radicale.example.com",
            RADICALE_USERNAME="user",
            RADICALE_PASSWORD=SecretStr("secret"),
            RADICALE_DEFAULT_CALENDAR="Damien",
            LOG_LEVEL="DEBUG",
            JSON_LOGS=True,
            CALDAV_TIMEOUT=60,
        )
        assert s.RADICALE_DEFAULT_CALENDAR == "Damien"
        assert s.LOG_LEVEL == "DEBUG"
        assert s.JSON_LOGS is True
        assert s.CALDAV_TIMEOUT == 60

    def test_log_level_normalised(self) -> None:
        s = Settings(
            RADICALE_URL="https://x.com",
            RADICALE_USERNAME="u",
            RADICALE_PASSWORD=SecretStr("p"),
            LOG_LEVEL="  debug  ",
        )
        assert s.LOG_LEVEL == "DEBUG"

    def test_invalid_log_level_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings(
                RADICALE_URL="https://x.com",
                RADICALE_USERNAME="u",
                RADICALE_PASSWORD=SecretStr("p"),
                LOG_LEVEL="BOGUS",
            )

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            Settings()  # type: ignore[call-arg]
