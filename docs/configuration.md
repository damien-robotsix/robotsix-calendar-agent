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
| `CALENDAR_AGENT_TRANSPORT` | `str` | `"inprocess"` | Transport mode: `inprocess` (in-memory `Registry`) or `brokered` |
| `CALENDAR_AGENT_ID` | `str` | `"robotsix-calendar"` | Agent identity registered on the broker |
| `BROKER_HOST` | `str` | `""` | Broker hostname or IP address |
| `BROKER_PORT` | `int` | `9090` | Broker port (1–65535) |
| `BROKER_SCHEME` | `str` | `"https"` | Broker URL scheme (`http` or `https`) |
| `BROKER_AGENT_TOKEN` | `SecretStr` | `SecretStr("")` | Authentication token for the broker |
| `BROKER_TLS_CA` | `str \| None` | `None` | Path to CA certificate PEM for verifying the broker |
| `BROKER_CLIENT_CERT` | `str \| None` | `None` | Path to client certificate PEM for mTLS (optional) |
| `BROKER_CLIENT_KEY` | `str \| None` | `None` | Path to client key PEM for mTLS (optional) |
| `LOG_LEVEL` | `str` | `"INFO"` | Log level for the root logger — one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` (case-insensitive) |
| `JSON_LOGS` | `bool` | `False` | When `true`, emit each log line as a single-line JSON object for structured-log ingestion |

### Component-agent settings

The component-agent responder adds `monitor`, `config-get`, and
`config-set` management kinds to the running agent.  It is **disabled
by default** and gated behind two conditions:

1. The `robotsix-agent-comm` SDK must be installed (it is a core
   dependency).
2. `COMPONENT_AGENT_ENABLED` must be `true` **and** a non-empty
   `COMPONENT_AGENT_TOKEN` must be configured.

| Variable | Type | Default | Description |
|---|---|---|---|
| `COMPONENT_AGENT_ENABLED` | `bool` | `False` | Enable the component-agent responder |
| `COMPONENT_AGENT_TOKEN` | `SecretStr` | `SecretStr("")` | Bearer token shared with the broker auth scheme |
| `COMPONENT_AGENT_ID` | `str` | `"robotsix-calendar"` | Agent identity (must match the broker registration) |

When `COMPONENT_AGENT_ENABLED=true` and the token is empty, the
process refuses to start with a `ValueError` mentioning
`COMPONENT_AGENT_TOKEN`.

### Runtime-configurable keys

Only a subset of keys can be changed at runtime via `config-set`:

| Key | Type | Rationale |
|---|---|---|
| `radicale_default_calendar` | `str` | Safe to change; updates the live `CalDavClient` default calendar |

All other keys are **startup-only** — changing them mid-flight would
either have no effect or corrupt the running agent (e.g. CalDAV
identity, broker connection, transport mode).

## Management kinds

When the component-agent responder is active, the agent answers three
additional request kinds on the existing broker connection:

### `monitor`

Returns genuine live telemetry:

- `agent_id`, `uptime_seconds`, `request_count`, `error_count`,
  `in_flight`, `last_request_ts`
- `caldav_url`, `default_calendar`
- `caldav_health` — a live CalDAV reachability probe
  (`connected` + `calendar_count`)
- `capabilities` — the list of supported management kinds

### `config-get`

Returns a **redacted** snapshot of all configuration (secret values
replaced with `"***"`) and per-key descriptors (type, whether
settable, whether secret).

### `config-set`

Validates then applies a set of config updates.  The request body
must contain an `updates` dict mapping dotted-path keys (e.g.
`"radicale_default_calendar"`) to new values.

- **Rejects** unknown keys, non-settable keys, and invalid values
  with a broker `Error` (no mutation occurs).
- On success returns an **audit map** `{key: (old, new)}` with
  secrets redacted, and the change is logged.

## Redaction

All secret fields (`radicale_password`, `broker_agent_token`,
`component_agent_token`) are replaced with the sentinel `"***"` in
every read path — `config-get`, `describe_config`, and the audit
returned by `config-set`.  Real secret values are never exposed
through the management API.
