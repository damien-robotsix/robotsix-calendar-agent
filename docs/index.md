# robotsix-calendar-agent

An in-process agent that manages a Radicale server's calendars (CalDAV) and
contacts (CardDAV) — full read-write including delete.

## Architecture

```
Caller → CalendarAgent → IntentParser (llmio)
                       → CalDavClient (caldav) → Radicale
```

1. The caller sends a natural-language instruction (or a structured
   ``add_to_calendar`` payload) to the agent.
2. `CalendarAgent` passes NL instructions to `IntentParser`, which uses
   `robotsix-llmio` to classify them into one of 10 operations and extract
   structured parameters.
3. The parsed intent is dispatched to `CalDavClient`, which wraps the
   `caldav` library to perform CRUD operations against the Radicale server.
4. The result is returned to the caller.

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

### 4. Use the agent directly

The agent provides a :class:`CalDavClient` for calendar operations
and an :class:`IntentParser` for natural-language instruction parsing.
Callers interact with these components directly:

```python
from robotsix_calendar_agent import CalendarAgent

agent = CalendarAgent()
agent.start()

# List calendars
calendars = agent._caldav.list_calendars()
print(calendars)

# Parse a natural-language instruction
parsed = agent._intent_parser.parse("create event Team Lunch tomorrow at noon")
print(parsed)
```

## Deployment

The agent runs in-process.  Start it and work with the CalDAV client
and intent parser directly:

```python
from robotsix_calendar_agent import CalendarAgent

agent = CalendarAgent()
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
| `agent_id` | `str` | `"calendar"` | Agent identifier |
| `radicale_url` | `str \| None` | `None` | Radicale URL (falls back to env) |
| `radicale_username` | `str \| None` | `None` | Radicale username (falls back to env) |
| `radicale_password` | `str \| None` | `None` | Radicale password (falls back to env) |
| `llm_model_config` | `dict \| None` | `None` | Forwarded to llmio for model selection |
