# Component-Agent Management

The calendar agent has an **optional** management plane that answers
three additional request kinds — `monitor`, `config-get`, and
`config-set` — on the same broker connection that carries calendar
instructions.  This tutorial shows you how to enable it and use each
kind.

**Prerequisites:** The brokered agent from the
[Brokered Service](brokered-service.md) tutorial should be running (or
the in-process setup from [Your First Agent](../basic/first-agent.md) —
both work).

---

## 1. Enable the management responder

Two conditions gate the responder:

1. `COMPONENT_AGENT_ENABLED` must be `true`.
2. `COMPONENT_AGENT_TOKEN` must be a non-empty string.

Add these to your environment (or `docker-compose.yml`):

```bash
export COMPONENT_AGENT_ENABLED=true
export COMPONENT_AGENT_TOKEN=your-mgmt-token  # pragma: allowlist secret
export COMPONENT_AGENT_ID=robotsix-calendar   # optional (default matches CALENDAR_AGENT_ID)
```

If `COMPONENT_AGENT_ENABLED` is `true` but the token is empty, the
agent refuses to start with a `ValueError`.  This is intentional —
management access must be authenticated.

When wiring the responder into an in-process agent, construct it
directly and pass it via the calendar agent constructor.  The
``component_agent_enabled`` / ``component_agent_token`` gating is
presumed satisfied (see the environment variables above).

```python
from robotsix_calendar_agent.brokered_entrypoint import ComponentAgentResponder
from robotsix_calendar_agent.settings import Settings

settings = Settings()
responder = ComponentAgentResponder(None, settings)
agent = CalendarAgent(agent=calendar_comm, component_responder=responder)
```

---

## 2. `monitor` — live telemetry

Send a `monitor` request to inspect the agent's health and counters:

```python
response = requester.send_request(
    "robotsix-calendar",
    {
        "kind": "monitor",
        "instruction": "monitor",  # required by the protocol
    },
)

snapshot = response.body
print(f"Uptime: {snapshot['uptime_seconds']:.0f}s")
print(f"Requests handled: {snapshot['request_count']}")
print(f"Errors: {snapshot['error_count']}")
print(f"In-flight: {snapshot['in_flight']}")
print(f"CalDAV connected: {snapshot['caldav_health']['connected']}")
print(f"Calendars visible: {snapshot['caldav_health']['calendar_count']}")
```

The response includes:

| Field | Description |
|---|---|
| `agent_id` | Agent identity string |
| `uptime_seconds` | Seconds since `start()` |
| `request_count` | Total requests processed |
| `error_count` | Requests that resulted in an `Error` |
| `in_flight` | Requests currently being handled |
| `last_request_ts` | Monotonic timestamp of the most recent request |
| `caldav_url` | The Radicale URL the agent is using |
| `default_calendar` | Default calendar for write operations |
| `caldav_health` | Live probe: `connected` (bool) and `calendar_count` (int) |
| `capabilities` | List of supported management kinds |

---

## 3. `config-get` — inspect current settings

```python
response = requester.send_request(
    "robotsix-calendar",
    {
        "kind": "config-get",
        "instruction": "config-get",
    },
)

print(response.body["snapshot"])
# {
#   "radicale_url": "https://radicale.example.com",
#   "radicale_username": "your-username",
#   "radicale_password": "***",          # ← redacted
#   ...
# }

for key, desc in response.body["descriptors"].items():
    print(f"{key}: type={desc['type']}, settable={desc['settable']}")
```

Secret values (`radicale_password`, `broker_agent_token`,
`component_agent_token`) are replaced with the sentinel `"***"`.
Real secrets are never exposed through the management API.

---

## 4. `config-set` — change settings at runtime

Only a subset of keys can be changed at runtime.  The canonical list is
in [Configuration](../../configuration.md#runtime-configurable-keys) —
currently the only settable key is `radicale_default_calendar`.

```python
response = requester.send_request(
    "robotsix-calendar",
    {
        "kind": "config-set",
        "instruction": "config-set",
        "updates": {
            "radicale_default_calendar": "Work",
        },
    },
)

print(response.body)
# {"radicale_default_calendar": {"old": "Robotsix", "new": "Work"}}
```

What happens:
1. The responder validates every key in `updates` — unknown keys and
   non-settable keys are rejected with an `Error`.
2. Valid updates are applied immediately — the live `CalDavClient`
   switches its default calendar.
3. The response is an **audit map**: `{ key: {"old": …, "new": …} }`
   with secrets redacted.
4. The change is logged at `INFO` level.

Attempting to set a non-settable key returns an error:

```python
response = requester.send_request(
    "robotsix-calendar",
    {
        "kind": "config-set",
        "instruction": "config-set",
        "updates": {"radicale_url": "http://evil.example.com"},
    },
)
# Returns an Error: "radicale_url: key is not settable at runtime"
```

---

## 5. End-to-end management script

```python
from robotsix_agent_comm.sdk import Agent
from robotsix_agent_comm.transport import Registry

from robotsix_calendar_agent import CalendarAgent
from robotsix_calendar_agent.brokered_entrypoint import ComponentAgentResponder
from robotsix_calendar_agent.settings import Settings

settings = Settings()
responder = ComponentAgentResponder(None, settings)

registry = Registry()
calendar_comm = Agent("calendar", registry)
agent = CalendarAgent(agent=calendar_comm, component_responder=responder)
requester = Agent("requester", registry)

with agent:
    requester.start()

    # -- monitor -------------------------------------------------------
    resp = requester.send_request(
        "calendar",
        {"kind": "monitor", "instruction": "monitor"},
    )
    print(f"Uptime: {resp.body['uptime_seconds']:.0f}s")

    # -- config-get ----------------------------------------------------
    resp = requester.send_request(
        "calendar",
        {"kind": "config-get", "instruction": "config-get"},
    )
    for key, desc in resp.body["descriptors"].items():
        if desc["settable"]:
            print(f"  {key}: settable")

    # -- config-set ----------------------------------------------------
    resp = requester.send_request(
        "calendar",
        {
            "kind": "config-set",
            "instruction": "config-set",
            "updates": {"radicale_default_calendar": "Work"},
        },
    )
    print("Audit:", resp.body)

    requester.stop()
```

---

## Next steps

- [Configuration](../../configuration.md) — full list of runtime-settable
  keys and the redaction rules applied to secrets.
- [Code Reference](../../reference/) — API-level documentation for the
  settings, agent, and responder classes.
