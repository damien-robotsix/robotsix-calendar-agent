# Brokered Service

This tutorial walks you through deploying the calendar agent as a
long-lived, TLS-authenticated brokered service — the mode you'd use in
production.

**Prerequisites:** Docker and Docker Compose installed, a running
[broker](https://github.com/damien-robotsix/robotsix-agent-comm)
instance reachable from the Docker host, and the Radicale credentials
from [Your First Agent](../basic/first-agent.md).

---

## 1. Understand the two transport modes

| Mode | How it works | When to use |
|---|---|---|
| **In-process** | `CalendarAgent` creates an in-memory `Registry` — everything runs in one Python process. | Development, tests, single-process scripts. |
| **Brokered** | The agent connects to a remote broker over TLS and blocks, handling requests pushed by the broker. | Production, multi-service deployments, any scenario where the requester and agent are separate processes or machines. |

The `CALENDAR_AGENT_TRANSPORT` environment variable selects the mode:

```bash
export CALENDAR_AGENT_TRANSPORT=brokered   # production
export CALENDAR_AGENT_TRANSPORT=inprocess  # default (dev)
```

---

## 2. Configure the broker connection

In addition to the Radicale variables, the brokered mode requires
**broker connection variables**.  Every variable is documented in
[Configuration](../../configuration.md); here are the essentials:

```bash
# Broker endpoint
export BROKER_HOST=ai-broker.robotsix.net
export BROKER_PORT=443
export BROKER_SCHEME=https

# Authentication
export BROKER_AGENT_TOKEN=your-broker-token  # pragma: allowlist secret

# TLS (optional — whether you need these depends on your broker setup)
export BROKER_TLS_CA=/certs/ca.pem
export BROKER_CLIENT_CERT=/certs/client.pem
export BROKER_CLIENT_KEY=/certs/client-key.pem
```

!!! warning "Broker agent token required"
    The agent will **not** start without a non-empty `BROKER_AGENT_TOKEN`
    when running in brokered mode.

---

## 3. Use the docker-compose definition

The repo root includes a ready-to-use
[`docker-compose.yml`](../../../docker-compose.yml).  Here's the
service definition with the blanks for you to fill in:

```yaml
services:
  calendar-agent:
    image: ghcr.io/damien-robotsix/robotsix-calendar-agent:main
    ports:
      - "8201:8080"
    environment:
      CALENDAR_AGENT_TRANSPORT: brokered
      CALENDAR_AGENT_ID: robotsix-calendar
      BROKER_HOST: ai-broker.robotsix.net
      BROKER_PORT: "443"
      BROKER_SCHEME: https
      BROKER_AGENT_TOKEN: ""          # ← fill in your token
      RADICALE_URL: http://radicale:5232
      RADICALE_USERNAME: ""           # ← fill in your username
      RADICALE_PASSWORD: ""           # ← fill in your password
      # SSL/TLS (optional):
      # BROKER_TLS_CA: /certs/ca.pem
      # BROKER_CLIENT_CERT: /certs/client.pem
      # BROKER_CLIENT_KEY: /certs/client-key.pem
    healthcheck:
      test: ["CMD", "python", "/app/healthcheck.py"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

Fill in the three placeholder values (`BROKER_AGENT_TOKEN`,
`RADICALE_USERNAME`, `RADICALE_PASSWORD`) and any TLS paths you need,
then start the service:

```bash
docker compose up calendar-agent
```

You should see log output like:

```
CalendarAgent  Starting CalendarAgent (agent_id='robotsix-calendar')
CalendarAgent  Connected to broker ai-broker.robotsix.net:443
```

The agent is now waiting for requests from the broker.

---

## 4. Verify the service is healthy

The healthcheck in the compose file runs `/app/healthcheck.py` every
30 seconds, so `docker ps` will show `(healthy)` once the agent is
connected:

```bash
docker compose ps
```

If the service crashes or can't reach the broker, it restarts
automatically (`restart: unless-stopped` is the default).  Check logs
with:

```bash
docker compose logs calendar-agent
```

---

## 5. Send a request through the broker

With the brokered agent running, any other agent-comm service that
shares the same broker can address `"robotsix-calendar"` (the
`CALENDAR_AGENT_ID`):

```python
from robotsix_agent_comm.sdk import Agent
from robotsix_agent_comm.transport.brokered import BrokeredTransport

requester = Agent(
    "my-app",
    BrokeredTransport(
        host="ai-broker.robotsix.net",
        port=443,
        scheme="https",
        token="your-broker-token",  # pragma: allowlist secret
    ),
)
requester.start()

response = requester.send_request(
    "robotsix-calendar",
    {"instruction": "list events this week"},
)
print(response.body["reply"])
requester.stop()
```

The broker routes the message, the calendar agent processes it, and
the response flows back on the same channel.

---

## 6. Structured logging

The brokered service supports structured JSON logging — set
`JSON_LOGS=true` to emit each log line as a single-line JSON object:

```yaml
environment:
  JSON_LOGS: "true"
  LOG_LEVEL: DEBUG
```

This integrates with log aggregators (ELK, Loki, Datadog) without
any config-file changes.

---

## Next steps

- [Component-Agent Management](component-agent-management.md) — enable
  the management responder and use `monitor`, `config-get`, and
  `config-set` on the brokered agent.
- [Configuration](../../configuration.md) — complete environment variable
  reference, including all TLS and logging options.
