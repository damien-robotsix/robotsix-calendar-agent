"""Single source of truth for all environment-variable configuration.

Uses :class:`pydantic_settings.BaseSettings` to read, validate, and
normalise configuration from the process environment.
"""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All RADICALE_* and BROKER_HOST/BROKER_AGENT_TOKEN fields have empty
    defaults so that the existing constructor-argument fallback and
    emptiness checks in ``CalendarAgent.__init__`` and
    ``_build_brokered_agent`` continue to work unchanged.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # -- Radicale credentials ------------------------------------------------
    RADICALE_URL: str = ""
    RADICALE_USERNAME: str = ""
    RADICALE_PASSWORD: SecretStr = SecretStr("")
    RADICALE_DEFAULT_CALENDAR: str = "Robotsix"

    # -- Calendar agent identity / transport ---------------------------------
    CALENDAR_AGENT_TRANSPORT: str = "inprocess"
    CALENDAR_AGENT_ID: str = "robotsix-calendar"

    # -- Broker connection ---------------------------------------------------
    BROKER_HOST: str = ""
    BROKER_PORT: int = 9090
    BROKER_SCHEME: str = "https"
    BROKER_AGENT_TOKEN: SecretStr = SecretStr("")
    BROKER_TLS_CA: str | None = None
    BROKER_CLIENT_CERT: str | None = None
    BROKER_CLIENT_KEY: str | None = None

    # -- Validators ----------------------------------------------------------

    @field_validator("CALENDAR_AGENT_TRANSPORT")
    @classmethod
    def _normalize_transport(cls, v: str) -> str:
        """Strip and lower-case the transport mode name.

        The caller (``main()``) is still responsible for rejecting
        unrecognised values so that the existing ``ValueError``
        message — which includes the offending value — is preserved.
        """
        return v.strip().lower()

    @field_validator("BROKER_PORT", mode="before")
    @classmethod
    def _validate_port(cls, v: Any) -> int:
        """Validate that *v* is an integer in the range 1-65535.

        Replaces the bare ``int(os.environ.get("BROKER_PORT", …))`` cast
        with a clear, field-specific message on failure.
        """
        _PORT_MSG = "BROKER_PORT must be an integer between 1 and 65535"
        if isinstance(v, int):
            port = v
        else:
            try:
                port = int(v)
            except (TypeError, ValueError):
                raise ValueError(_PORT_MSG) from None
        if port < 1 or port > 65535:
            raise ValueError(_PORT_MSG)
        return port

    @field_validator(
        "BROKER_TLS_CA",
        "BROKER_CLIENT_CERT",
        "BROKER_CLIENT_KEY",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, v: Any) -> Any:
        """Treat empty strings as ``None``.

        Mirrors the ``or None`` idiom previously used in
        ``_build_brokered_agent`` for the mTLS-related variables.
        """
        if isinstance(v, str) and v == "":
            return None
        return v
