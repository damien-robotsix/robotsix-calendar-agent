# Your First Agent

This tutorial walks you through installing the agent, configuring your
Radicale credentials, and sending your first natural-language instruction.

**Prerequisites:** Python 3.14+, a running
[Radicale](https://radicale.org/) CalDAV server, and `uv` (the Python
package manager used throughout these docs).

---

## 1. Install

Clone the repository and install dependencies:

```bash
git clone https://github.com/damien-robotsix/robotsix-calendar-agent.git
cd robotsix-calendar-agent
uv sync
```

---

## 2. Configure Radicale access

The agent reads credentials from environment variables.  Set the three
required Radicale variables pointing at your server:

```bash
export RADICALE_URL="https://radicale.example.com"
export RADICALE_USERNAME="your-username"
export RADICALE_PASSWORD="your-password"  # pragma: allowlist secret
```

You can also pass these as constructor arguments (see step 3).  For a
full reference of every supported variable, see
[Configuration](../../configuration.md).

!!! tip "No Radicale server handy?"
    The project's test suite includes a
    [CalDAV test server fixture](../../../tests/caldav_client/caldav_test_server.py)
    that spins up a local Radicale container via docker-compose.  You can
    point `RADICALE_URL` at `http://localhost:5232` after running it.

---

## 3. Write a minimal script

Create `hello_calendar.py`:

```python
from robotsix_agent_comm.sdk import Agent
from robotsix_agent_comm.transport import Registry

from robotsix_calendar_agent import CalendarAgent

# -- create a shared in-memory transport --------------------------------
registry = Registry()

# -- instantiate the calendar agent -------------------------------------
# CalendarAgent wires itself onto `agent` and will handle requests
# addressed to `"calendar"`.
calendar_comm = Agent("calendar", registry)
agent = CalendarAgent(agent=calendar_comm)

# -- create a requester agent on the same transport ---------------------
requester = Agent("requester", registry)

with agent:
    requester.start()

    response = requester.send_request(
        "calendar",
        {"instruction": "list events this week"},
    )

    print(response.body["reply"])
    for event in response.body.get("result", []):
        print(f"  - {event['summary']} ({event['dtstart']})")

    requester.stop()
```

Run it:

```bash
uv run python hello_calendar.py
```

---

## 4. What just happened?

1. **Shared transport** — both the calendar agent and the requester
   share one in-memory `Registry`, so messages flow between them
   without any network hop.

2. **`with agent:`** — the context manager calls `agent.start()` on
   entry and `agent.stop()` on exit.  You can replace the `with` block
   with explicit `start()` / `stop()` calls if you prefer.

3. **`send_request`** — `requester.send_request("calendar", body)`
   delivers a dict to the calendar agent.  The only required key in
   the body is `"instruction"` — a free-form natural-language string.

4. **Parsing & dispatch** — the agent passes your instruction through
   an LLM-based intent parser that classifies it (e.g. `list_events`)
   and extracts structured parameters (date range, calendar, …), then
   dispatches to the CalDAV client.

5. **Response** — the returned response has two important keys:

   | Key | Description |
   |---|---|
   | `reply` | Human-readable summary string |
   | `result` | Structured data (a list of event dicts for list operations, a single dict with `uid`/`summary`/`dtstart`/`dtend` for creates and updates, `{"deleted": true}` for deletes) |

---

## 5. Next steps

- [Managing Calendar Events](manage-events.md) — create, update, and delete
  events with natural language.
- [Brokered Service](../intermediate/brokered-service.md) — deploy the agent
  as a long-lived, TLS-authenticated service.
- [Configuration](../../configuration.md) — complete environment variable
  reference.
