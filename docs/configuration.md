# Configuration

All configuration is read from environment variables via
`pydantic_settings.BaseSettings`. The settings class lives at
`src/robotsix_calendar_agent/settings.py`.

## Environment variables

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
