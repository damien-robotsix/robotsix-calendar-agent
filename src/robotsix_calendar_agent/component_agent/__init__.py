"""Component-agent management surface for robotsix-calendar.

Provides the config contract and settings for the ``monitor`` /
``config-get`` / ``config-set`` management kinds.  The responder itself
lives in :mod:`~robotsix_calendar_agent.brokered_entrypoint`.
"""

from __future__ import annotations

from .config_contract import (
    SETTABLE_KEYS,
    ConfigContractError,
    apply_config_update,
    describe_config,
    get_config_snapshot,
    validate_config_update,
)
from .settings import ComponentAgentSettings

__all__ = [
    "SETTABLE_KEYS",
    "ComponentAgentSettings",
    "ConfigContractError",
    "apply_config_update",
    "describe_config",
    "get_config_snapshot",
    "validate_config_update",
]
