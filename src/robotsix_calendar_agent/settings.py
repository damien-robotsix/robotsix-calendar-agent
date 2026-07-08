"""Single source of truth for all environment-variable configuration.

Uses :class:`pydantic_settings.BaseSettings` to read, validate, and
normalise configuration from the process environment.
"""

from __future__ import annotations

import logging

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All RADICALE_* fields have empty defaults so that the existing
    constructor-argument fallback and emptiness checks in
    ``CalendarAgent.__init__`` continue to work unchanged.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # -- Radicale credentials ------------------------------------------------
    RADICALE_URL: str = ""
    """Radicale server URL (e.g. https://radicale.example.com)."""

    RADICALE_USERNAME: str = ""
    """Radicale username for authentication."""

    RADICALE_PASSWORD: SecretStr = SecretStr("")
    """Radicale password for authentication."""

    RADICALE_DEFAULT_CALENDAR: str = "Robotsix"
    """Default calendar name when no calendar_id is provided."""

    # -- Logging -------------------------------------------------------------
    LOG_LEVEL: str = "INFO"
    """Log level - one of DEBUG, INFO, WARNING, ERROR, CRITICAL."""

    JSON_LOGS: bool = False
    """When True, emit logs as JSON for structured-log ingestion."""

    # -- Validators ----------------------------------------------------------

    @field_validator("LOG_LEVEL")
    @classmethod
    def _normalize_log_level(cls, v: str) -> str:
        """Normalise to uppercase and reject invalid log levels."""
        v = v.strip().upper()
        if v not in logging.getLevelNamesMapping():
            raise ValueError(
                f"Invalid LOG_LEVEL={v!r}; must be one of "
                f"{sorted(logging.getLevelNamesMapping())}"
            )
        return v
