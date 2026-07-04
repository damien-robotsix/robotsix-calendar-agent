# Your First Agent

This tutorial walks you through installing the agent, configuring your
Radicale credentials, and sending your first natural-language instruction.

**Prerequisites:** Python 3.12+, a running
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
from robotsix_calendar_agent import CalendarAgent

# -- instantiate the calendar agent -------------------------------------
agent = CalendarAgent()

# -- list calendars -----------------------------------------------------
with agent:
    calendars = agent._caldav.list_calendars()
    print("Your calendars:", calendars)
```

Run it:

```bash
uv run python hello_calendar.py
```

---

## 4. What just happened?

1. **Direct API** — the calendar agent runs in-process with no broker
   transport.  The CalDAV client and intent parser are accessed
   directly through the agent instance.

2. **`with agent:`** — the context manager calls `agent.start()` on
   entry and `agent.stop()` on exit.  You can replace the `with` block
   with explicit `start()` / `stop()` calls if you prefer.

3. **CalDAV client** — `agent._caldav` provides typed methods for
   calendar, contact, and task operations against your Radicale server.

---

## 5. Next steps

- [Managing Calendar Events](manage-events.md) — create, update, and delete
  events.
- [Configuration](../../configuration.md) — complete environment variable
  reference.
