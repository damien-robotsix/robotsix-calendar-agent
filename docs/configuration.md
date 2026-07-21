# Configuration

All configuration is loaded from a single JSON config file via
`robotsix_config.load_config()`. The settings model lives at
`src/robotsix_calendar_agent/settings.py`.

## Config file

The config file is located via the `ROBOTSIX_CONFIG_FILE` environment
variable, falling back to `config/config.json`.  All values live in the
config file — no environment overlay, no CLI merge.

## Settings model

::: robotsix_calendar_agent.settings

!!! note "Component agent removed"
    The component-agent management package has been removed.  See
    [`reference/component_agent.md`](reference/component_agent.md) for details
    on the removed component-agent responder and its replacement plan.
