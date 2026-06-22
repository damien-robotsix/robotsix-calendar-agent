# robotsix-calendar-agent

An agent-comm agent that manages a Radicale server's calendars (CalDAV) and
contacts (CardDAV) — full read-write including delete — driven entirely by
the `robotsix-agent-comm` messaging system.

## Architecture

```
agent-comm Request → CalendarAgent → IntentParser (llmio)
                                   → CalDavClient (caldav) → Radicale
                                   ← Response / Error
```

1. A natural-language instruction arrives as an agent-comm `Request`.
2. `CalendarAgent` passes the instruction to `IntentParser`, which uses
   `robotsix-llmio` to classify it into one of 8 operations and extract
   structured parameters.
3. The parsed intent is dispatched to `CalDavClient`, which wraps the
   `caldav` library to perform CRUD operations against the Radicale server.
4. The result is returned as a correlated `Response` (or `Error` on failure).

## Getting started

### 1. Configure Radicale access

Set the environment variables pointing to your Radicale server:

```bash
export RADICALE_URL="https://radicale.example.com"
export RADICALE_USERNAME="your-username"
export RADICALE_PASSWORD="your-password"
```

Alternatively, pass these values as constructor arguments to `CalendarAgent`.

### 2. Install dependencies

```bash
uv sync
```

### 3. Start the agent

```python
from robotsix_calendar_agent import CalendarAgent

agent = CalendarAgent()
agent.start()
```

### 4. Send a request via agent-comm

```python
from robotsix_agent_comm.sdk import Agent
from robotsix_agent_comm.transport import Registry
from robotsix_agent_comm.protocol import Request, Metadata

registry = Registry()
# The calendar agent has already registered itself on this registry.
# Create a requester agent to send a message:
requester = Agent("requester", registry)
requester.start()

# Send a request to the calendar agent:
response = requester.send_request(
    "calendar",
    {"instruction": "list events this week"},
)
print(response.body)
```

## Deployment

The agent supports two transport modes, selected by the
`CALENDAR_AGENT_TRANSPORT` environment variable.

### In-process transport (`inprocess`, default)

The agent constructs its own in-memory
`robotsix_agent_comm.transport.Registry`. This is the zero-config path
used by tests and single-process deployments where a requester and the
calendar agent live in the same process:

```python
from robotsix_calendar_agent import CalendarAgent

agent = CalendarAgent()  # transport=None → in-process Registry
agent.start()
```

### Brokered transport (`brokered`)

The agent connects to a secured, TLS-authenticated broker and runs as an
independent long-lived service. The broker pushes dispatched messages to
the agent's handler. Connection details come from the `BROKER_*`
environment variables (see the configuration reference below).

A console-script entrypoint, `calendar-agent`, drives the long-lived
service. It reads `CALENDAR_AGENT_TRANSPORT`, builds the selected
transport, starts the agent, and blocks until `SIGTERM`/`SIGINT`, on
which it stops the agent and exits cleanly:

```bash
export CALENDAR_AGENT_TRANSPORT=brokered
export BROKER_HOST=broker.example.com
export BROKER_TLS_CA=/certs/ca.pem
export BROKER_AGENT_TOKEN=your-broker-token
calendar-agent
```

### Docker / Compose

A `Dockerfile` at the repo root packages the agent (defaulting to
`CALENDAR_AGENT_TRANSPORT=brokered`) and runs the `calendar-agent`
console-script:

```bash
docker build -t calendar-agent .
```

A `docker-compose.yml` defines the `calendar-agent` service alongside a
`broker` service (the broker's real definition lives in the
`robotsix-agent-comm` repo). TLS material is mounted read-only and all
broker environment variables are wired in; the service restarts
`unless-stopped`:

```bash
docker compose up calendar-agent
```

## Operations reference

| Operation | Example instruction | Key params |
|---|---|---|
| `list_events` | "list events this week" | `start`, `end` (ISO 8601) |
| `create_event` | "add a dentist appointment next Tuesday at 3pm" | `summary`, `dtstart`, `dtend` |
| `update_event` | "reschedule the dentist to 4pm" | `uid`, updated fields |
| `delete_event` | "cancel the dentist appointment" | `uid` |
| `list_contacts` | "show all contacts" | (none) |
| `create_contact` | "add John Doe, john@example.com" | `full_name`, `email`, `phone` |
| `update_contact` | "change John's email to john.doe@example.com" | `uid`, updated fields |
| `delete_contact` | "remove John Doe from contacts" | `uid` |

## Configuration reference

See [Configuration](configuration.md) for the canonical environment-variable
reference.

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RADICALE_URL` | Yes | — | Radicale server URL |
| `RADICALE_USERNAME` | Yes | — | Radicale username |
| `RADICALE_PASSWORD` | Yes | — | Radicale password |
| `CALENDAR_AGENT_TRANSPORT` | No | `inprocess` | Transport mode: `inprocess` (in-memory `Registry`) or `brokered` |
| `CALENDAR_AGENT_ID` | No | `robotsix-calendar` | Agent identity registered on the broker |
| `BROKER_HOST` | When brokered | — | Broker hostname/IP |
| `BROKER_PORT` | No | `9090` | Broker port |
| `BROKER_SCHEME` | When brokered | `https` | Broker URL scheme (`http` or `https`) |
| `BROKER_TLS_CA` | When brokered | — | Path to CA certificate PEM for verifying the broker |
| `BROKER_CLIENT_CERT` | No | — | Path to client certificate PEM (mTLS, optional) |
| `BROKER_CLIENT_KEY` | No | — | Path to client key PEM (mTLS, optional) |
| `BROKER_AGENT_TOKEN` | When brokered | — | Authentication token for the broker |

### Constructor options (`CalendarAgent`)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `agent_id` | `str` | `"calendar"` | Agent-comm agent ID |
| `radicale_url` | `str \| None` | `None` | Radicale URL (falls back to env) |
| `radicale_username` | `str \| None` | `None` | Radicale username (falls back to env) |
| `radicale_password` | `str \| None` | `None` | Radicale password (falls back to env) |
| `llm_model_config` | `dict \| None` | `None` | Forwarded to llmio for model selection |
