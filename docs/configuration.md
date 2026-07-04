# Configuration

All configuration is read from environment variables via
`pydantic_settings.BaseSettings`. The settings class lives at
`src/robotsix_calendar_agent/settings.py`.

## Environment variables

### Core settings

| Variable | Type | Default | Description |
|---|---|---|---|
| `RADICALE_URL` | `str` | `""` | Radicale server URL |
| `RADICALE_USERNAME` | `str` | `""` | Radicale username |
| `RADICALE_PASSWORD` | `SecretStr` | `SecretStr("")` | Radicale password |
| `RADICALE_DEFAULT_CALENDAR` | `str` | `"Robotsix"` | Default calendar name for write operations when no `calendar_id` is provided |
| `LOG_LEVEL` | `str` | `"INFO"` | Log level for the root logger — one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive) |
| `JSON_LOGS` | `bool` | `False` | When `true`, emit each log line as a single-line JSON object for structured-log ingestion |

!!! note "Component agent removed"
    The component-agent management package has been removed.  See
    [`reference/component_agent.md`](reference/component_agent.md) for details
    on the removed component-agent responder and its replacement plan.
