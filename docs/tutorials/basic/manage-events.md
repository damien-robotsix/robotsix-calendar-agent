# Managing Calendar Events

This tutorial covers the four calendar-event operations —
**create**, **list**, **update**, and **delete** — all driven by
natural-language instructions.

We assume you've completed [Your First Agent](first-agent.md) and have
the three `RADICALE_*` environment variables set.  Use the same
shared-Registry pattern from that tutorial as your starting point.

---

## Setup

Save this as `manage_events.py`:

```python
from robotsix_agent_comm.sdk import Agent
from robotsix_agent_comm.transport import Registry

from robotsix_calendar_agent import CalendarAgent

registry = Registry()
calendar_comm = Agent("calendar", registry)
agent = CalendarAgent(agent=calendar_comm)
requester = Agent("requester", registry)

agent.start()
requester.start()
```

We'll add each operation to the bottom of this script.  At the end,
call `requester.stop()` and `agent.stop()` to clean up.

---

## 1. Create an event

```python
response = requester.send_request(
    "calendar",
    {"instruction": "add a dentist appointment next Tuesday at 3pm"},
)

event = response.body["result"]
print(f"Created: {event['summary']} — uid={event['uid']}")
# Created: Dentist appointment — uid=abc123-...@radicale.example.com
```

The agent:
- Parses `"add a dentist appointment next Tuesday at 3pm"` into the
  `create_event` operation.
- Extracts `summary="Dentist appointment"`, a `dtstart` and `dtend`
  one hour apart on the coming Tuesday at 15:00.
- Creates the event on your Radicale server and returns the new event's
  metadata including its unique `uid`.

Keep the `uid` — you'll need it for updates and deletes.

---

## 2. List events

```python
response = requester.send_request(
    "calendar",
    {"instruction": "list events this month"},
)

events = response.body.get("result", [])
print(f"Found {len(events)} event(s):")
for ev in events:
    print(f"  {ev['uid']}  {ev['summary']}  {ev['dtstart']}")
```

The LLM parser maps relative date expressions ("this week",
"next month", "between Jan 1 and Jan 15") to ISO 8601 `start`/`end`
parameters that the CalDAV client uses to query the server.

---

## 3. Update an event

Use the `uid` from step 1:

```python
response = requester.send_request(
    "calendar",
    {
        "instruction": (
            "reschedule the dentist appointment (uid=abc123-...)"
            " to 4pm on the same day"
        ),
    },
)

updated = response.body["result"]
print(f"Updated: {updated['uid']} — new start: {updated['dtstart']}")
```

The agent matches the `uid` to the existing event and applies the
time change.  You can also update `summary`, `description`, and
`location` — just mention what you want changed in the instruction.

!!! note
    Including the `uid` in the instruction text is the most reliable
    way to identify which event to update.  The intent parser uses it
    as a direct lookup key.

---

## 4. Delete an event

```python
response = requester.send_request(
    "calendar",
    {"instruction": "cancel the dentist appointment (uid=abc123-...)"},
)

print(response.body["result"])  # {"deleted": true}
print(response.body["reply"])   # "Deleted event …"
```

Words like *cancel*, *remove*, and *delete* all trigger the
`delete_event` operation.

---

## Complete script

```python
from robotsix_agent_comm.sdk import Agent
from robotsix_agent_comm.transport import Registry

from robotsix_calendar_agent import CalendarAgent

registry = Registry()
calendar_comm = Agent("calendar", registry)
agent = CalendarAgent(agent=calendar_comm)
requester = Agent("requester", registry)

agent.start()
requester.start()

# 1. Create
resp = requester.send_request(
    "calendar",
    {"instruction": "add a dentist appointment next Tuesday at 3pm"},
)
uid = resp.body["result"]["uid"]
print(f"Created event uid={uid}")

# 2. List
resp = requester.send_request(
    "calendar",
    {"instruction": "list events this month"},
)
print(f"Found {len(resp.body.get('result', []))} event(s)")

# 3. Update
resp = requester.send_request(
    "calendar",
    {"instruction": f"reschedule the appointment uid={uid} to 4pm"},
)
print(f"Updated: new start {resp.body['result']['dtstart']}")

# 4. Delete
resp = requester.send_request(
    "calendar",
    {"instruction": f"cancel the appointment uid={uid}"},
)
print(f"Deleted: {resp.body['result']}")

requester.stop()
agent.stop()
```

---

## Contacts too

The same pattern works for contacts — just use natural-language
instructions like `"add John Doe, john@example.com, 555-0100"`,
`"list contacts"`, `"update John's phone to 555-0200"`, or
`"remove John Doe"`.  The agent dispatches to CardDAV (the contacts
equivalent of CalDAV) automatically.

---

## Next steps

- [Component-Agent Management](../intermediate/component-agent-management.md) —
  monitor, inspect, and reconfigure the agent at runtime.
