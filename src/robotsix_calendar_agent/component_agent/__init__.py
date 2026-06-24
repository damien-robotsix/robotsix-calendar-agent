"""Component-agent management surface for robotsix-calendar.

Provides the responder, config contract, and settings for the
``monitor`` / ``config-get`` / ``config-set`` management kinds.
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
from .responder import (
    COMPONENT_KINDS,
    ComponentAgentResponder,
)
from .settings import ComponentAgentSettings

__all__ = [
    "COMPONENT_KINDS",
    "SETTABLE_KEYS",
    "ComponentAgentResponder",
    "ComponentAgentSettings",
    "ConfigContractError",
    "apply_config_update",
    "describe_config",
    "get_config_snapshot",
    "validate_config_update",
]
