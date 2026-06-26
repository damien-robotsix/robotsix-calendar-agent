"""Config contract for the component-agent responder.

Provides validation, snapshot, and live-apply for the running
:class:`Settings` object, following the ``robotsix-agent-comm``
component-agent pattern.

**Dotted-path key mapping**

Config keys are derived from ``Settings`` field names by lowercasing:
``RADICALE_DEFAULT_CALENDAR`` → ``radicale_default_calendar``.
Secret fields are redacted in all read paths using the ``"***"``
sentinel.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ConfigContractError(Exception):
    """Raised when a config operation fails validation.

    Mirrors the shape of ``robotsix_agent_comm.protocol.Error`` so the
    responder can translate it cleanly.
    """

    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

_REDACTED = "***"

_SECRET_FIELDS: frozenset[str] = frozenset(
    {
        "radicale_password",
        "broker_agent_token",
        "component_agent_token",
    }
)


def _is_secret_field(key: str) -> bool:
    """Return ``True`` for dotted-path keys whose values must be redacted."""
    return key in _SECRET_FIELDS


# ---------------------------------------------------------------------------
# Settable keys
# ---------------------------------------------------------------------------

#: Keys that may be changed at runtime via ``config-set``.
#:
#: **Excluded (startup-only)** -- changing these mid-flight would either
#: have no effect or corrupt the running agent:
#:
#: * ``radicale_url``, ``radicale_username``, ``radicale_password`` —
#:   the ``CalDavClient`` is already connected; changing identity
#:   requires a full reconnect.
#: * ``calendar_agent_transport``, ``calendar_agent_id`` — transport
#:   mode and agent identity are fixed at process start.
#: * ``broker_host``, ``broker_port``, ``broker_scheme``,
#:   ``broker_agent_token``, ``broker_tls_ca``, ``broker_client_cert``,
#:   ``broker_client_key`` — the broker connection is established once
#:   and cannot be reconfigured at runtime.
#: * ``component_agent_enabled``, ``component_agent_token``,
#:   ``component_agent_id`` — component-agent gating is also
#:   startup-only.
SETTABLE_KEYS: frozenset[str] = frozenset(
    {
        "radicale_default_calendar",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_field_name(key: str) -> str:
    """Map a dotted-path *key* to its ``Settings`` field name (uppercase)."""
    return key.upper()


def _core_settings_field_names() -> list[str]:
    """Return the list of core ``Settings`` field names (uppercase)."""
    from ..settings import Settings as CoreSettings

    return list(CoreSettings.model_fields.keys())


def _component_settings_field_names() -> list[str]:
    """Return the list of ``ComponentAgentSettings`` field names."""
    from .settings import ComponentAgentSettings

    return list(ComponentAgentSettings.model_fields.keys())


def _iter_config_fields(
    settings: Any,
    comp_settings: Any,
) -> Iterator[tuple[str, Any]]:
    """Yield ``(key, value)`` for every core + component config field."""
    from ..settings import Settings as CoreSettings
    from .settings import ComponentAgentSettings

    for name in CoreSettings.model_fields:
        key = name.lower()
        yield key, getattr(settings, name)
    for name in ComponentAgentSettings.model_fields:
        key = name.lower()
        yield key, getattr(comp_settings, name)


def _read_value(settings: Any, comp_settings: Any, key: str) -> Any:
    """Return the live, possibly-redacted value for *key*."""
    field_name = _resolve_field_name(key)
    # Core settings take precedence
    if field_name in _core_settings_field_names():
        value = getattr(settings, field_name)
    elif field_name in _component_settings_field_names():
        value = getattr(comp_settings, field_name)
    else:
        raise ConfigContractError(
            code="unknown_key",
            message=f"Unknown config key: {key!r}",
        )
    if _is_secret_field(key) or hasattr(value, "get_secret_value"):
        return _REDACTED
    return value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_config_snapshot(
    settings: Any,
    comp_settings: Any | None = None,
) -> dict[str, Any]:
    """Return a flat, dotted-path view of current config with secrets redacted.

    Args:
        settings: The live core :class:`Settings` instance.
        comp_settings: The live :class:`ComponentAgentSettings` instance
            (if available).

    Returns:
        A ``{key: value}`` dict where keys are lowercased field names
        and secret values are replaced with ``"***"``.
    """
    if comp_settings is None:
        from .settings import ComponentAgentSettings

        comp_settings = ComponentAgentSettings()

    result: dict[str, Any] = {}
    for key, value in _iter_config_fields(settings, comp_settings):
        if _is_secret_field(key) or hasattr(value, "get_secret_value"):
            result[key] = _REDACTED
        else:
            result[key] = value

    return result


def describe_config(
    settings: Any,
    comp_settings: Any | None = None,
) -> dict[str, Any]:
    """Return per-key descriptors for every config key.

    Returns:
        ``{"keys": {key: {"type": ..., "settable": bool, "secret": bool,
        "value": ...}}}``
    """
    if comp_settings is None:
        from .settings import ComponentAgentSettings

        comp_settings = ComponentAgentSettings()

    keys: dict[str, dict[str, Any]] = {}
    for key, value in _iter_config_fields(settings, comp_settings):
        secret = _is_secret_field(key) or hasattr(value, "get_secret_value")
        keys[key] = {
            "type": type(value).__name__,
            "settable": key in SETTABLE_KEYS,
            "secret": secret,
            "value": _REDACTED if secret else value,
        }

    return {"keys": keys}


def validate_config_update(
    settings: Any,
    updates: dict[str, Any],
) -> None:
    """Validate *updates* without applying them.

    Rejects unknown keys, keys not in :data:`SETTABLE_KEYS`, and values
    that would fail pydantic validation when combined with the current
    live config.

    Args:
        settings: The live core :class:`Settings` instance.
        updates: ``{dotted_key: new_value}`` dict.

    Raises:
        ConfigContractError: If any validation rule is violated.
    """
    from ..settings import Settings as CoreSettings

    # 1. Reject unknown / non-settable keys
    for key in updates:
        field_name = _resolve_field_name(key)
        if field_name not in CoreSettings.model_fields:
            raise ConfigContractError(
                code="unknown_key",
                message=f"Unknown config key: {key!r}",
                details={"key": key},
            )
        if key not in SETTABLE_KEYS:
            raise ConfigContractError(
                code="not_settable",
                message=f"Config key {key!r} is not settable at runtime",
                details={"key": key},
            )

    if not updates:
        return

    # 2. Build a candidate Settings object from current real values + updates
    candidate_kwargs: dict[str, Any] = {}
    for name in CoreSettings.model_fields:
        candidate_kwargs[name] = getattr(settings, name)
    for key, new_val in updates.items():
        field_name = _resolve_field_name(key)
        candidate_kwargs[field_name] = new_val

    try:
        CoreSettings(**candidate_kwargs)
    except PydanticValidationError as exc:
        raise ConfigContractError(
            code="invalid_value",
            message=f"Config validation failed: {exc}",
            details={"errors": exc.errors()},
        ) from exc


def apply_config_update(
    settings: Any,
    updates: dict[str, Any],
) -> dict[str, tuple[Any, Any]]:
    """Validate *updates* then apply them to the live *settings*.

    Returns an **audit map** ``{key: (old_value, new_value)}`` with
    secret values redacted.

    Raises:
        ConfigContractError: If validation fails — no mutation occurs.
    """
    # Validate first — never mutate on invalid.
    validate_config_update(settings, updates)

    if not updates:
        return {}

    audit: dict[str, tuple[Any, Any]] = {}
    for key, new_val in updates.items():
        field_name = _resolve_field_name(key)
        old_val = getattr(settings, field_name)
        # Redact secret values in the audit trail
        old_redacted = _REDACTED if _is_secret_field(key) else old_val
        new_redacted = _REDACTED if _is_secret_field(key) else new_val
        setattr(settings, field_name, new_val)
        audit[key] = (old_redacted, new_redacted)

    # Emit audit log
    logger.info(
        "config-set applied %d change(s): %s",
        len(audit),
        {k: (old, new) for k, (old, new) in audit.items()},
    )

    return audit
