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
   `robotsix-llmio` to classify it into one of 10 operations and extract
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
export RADICALE_PASSWORD="your-password"  # pragma: allowlist secret
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

The agent runs in-process via an in-memory
`robotsix_agent_comm.transport.Registry`. This is the zero-config path
used by tests and single-process deployments where a requester and the
calendar agent live in the same process:

```python
from robotsix_calendar_agent import CalendarAgent

agent = CalendarAgent()  # transport=None → in-process Registry
agent.start()
```

## Operations reference

| Operation | Example instruction | Key params |
|---|---|---|
| `list_calendars` | "what calendars do I have" | (none) |
| `list_events` | "list events this week" | `start`, `end` (ISO 8601) |
| `create_event` | "add a dentist appointment next Tuesday at 3pm" | `summary`, `dtstart`, `dtend` |
| `update_event` | "reschedule the dentist to 4pm" | `uid`, updated fields |
| `delete_event` | "cancel the dentist appointment" | `uid` |
| `list_tasks` | "show me my pending tasks" | `calendar_id?` |
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


### Constructor options (`CalendarAgent`)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `agent_id` | `str` | `"calendar"` | Agent-comm agent ID |
| `radicale_url` | `str \| None` | `None` | Radicale URL (falls back to env) |
| `radicale_username` | `str \| None` | `None` | Radicale username (falls back to env) |
| `radicale_password` | `str \| None` | `None` | Radicale password (falls back to env) |
| `llm_model_config` | `dict \| None` | `None` | Forwarded to llmio for model selection |
