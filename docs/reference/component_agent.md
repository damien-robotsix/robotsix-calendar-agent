# Component Agent

The `component_agent` package embeds the `robotsix-agent-comm`
responder template into the calendar agent, making it a fully
manageable component.

## Overview

- **`ComponentAgentResponder`** (`responder.py`) — dispatches
  `monitor`, `config-get`, and `config-set` request kinds.
- **`ConfigContract`** (`config_contract.py`) — validates and applies
  config updates with redaction, audit, and live-apply.
- **`ComponentAgentSettings`** (`settings.py`) — gates the responder
  (disabled by default, token-required-when-enabled).

When enabled, the responder composes onto the **existing**
`BrokeredAgent` connection (no second agent-id registration).

## Request Kinds

### `monitor`

Returns genuine live telemetry — real counters, uptime, and a CalDAV
health probe.

### `config-get`

Returns a redacted config snapshot and per-key descriptors.

### `config-set`

Validates-then-applies config updates. Returns an audit map on
success or a broker `Error` on invalid input.

## Configuration

See the [Configuration guide](../configuration.md) for environment
variables and settable keys.

## API Reference

::: robotsix_calendar_agent.component_agent.responder.ComponentAgentResponder
    options:
      members:
        - on_request

::: robotsix_calendar_agent.component_agent.config_contract
    options:
      members:
        - get_config_snapshot
        - describe_config
        - validate_config_update
        - apply_config_update
        - ConfigContractError
        - SETTABLE_KEYS

::: robotsix_calendar_agent.component_agent.settings.ComponentAgentSettings
