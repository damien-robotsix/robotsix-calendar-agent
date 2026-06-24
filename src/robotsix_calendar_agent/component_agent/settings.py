"""Component-agent gating settings — disabled by default.

These settings control whether the ``monitor`` / ``config-get`` /
``config-set`` responder is active.  They are **separate** from the
core :class:`Settings` because the component agent is an additive
management layer, not a core transport concern.
"""

from __future__ import annotations

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ComponentAgentSettings(BaseSettings):
    """Settings that gate and configure the component-agent responder.

    All fields follow the existing naming convention (uppercase,
    ``COMPONENT_AGENT_`` prefix).

    The token-required-when-enabled invariant is enforced at
    construction time so misconfiguration is caught early.
    """

    model_config = SettingsConfigDict(extra="ignore")

    COMPONENT_AGENT_ENABLED: bool = False
    COMPONENT_AGENT_TOKEN: SecretStr = SecretStr("")
    COMPONENT_AGENT_ID: str = "robotsix-calendar"

    @model_validator(mode="after")
    def _token_required_when_enabled(self) -> ComponentAgentSettings:
        if self.COMPONENT_AGENT_ENABLED and (
            not self.COMPONENT_AGENT_TOKEN.get_secret_value()
        ):
            raise ValueError(
                "COMPONENT_AGENT_TOKEN must be set when COMPONENT_AGENT_ENABLED=true"
            )
        return self
