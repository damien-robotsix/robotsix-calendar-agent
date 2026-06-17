# robotsix-calendar-agent

Agent-comm agent managing a Radicale CalDAV/CardDAV calendar and contacts.

The agent receives natural-language instructions via agent-comm `Request`
messages, parses intent through `robotsix-llmio`, executes the operation
against a Radicale server, and returns a correlated `Response` or `Error`.
No CLI, no web UI, no separate HTTP API — agent-comm intake only.

It can run in-process (default) or as a long-lived brokered service via
the `calendar-agent` console-script entrypoint, with a `Dockerfile` and
`docker-compose.yml` for containerised deployment against a secured
TLS broker.

## Status

Early scaffold — under active development.

## Development

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency
management. The lockfile (`uv.lock`) is committed; CI installs with
`uv sync --frozen`.

```bash
uv sync
```

### Running checks

```bash
uv run ruff check .           # lint
uv run ruff format --check .  # formatting check
uv run mypy .                 # static type checking (strict)
uv run pytest                 # tests
```

## Configuration

The agent requires these environment variables:

| Variable | Description |
|---|---|
| `RADICALE_URL` | URL of the Radicale server (e.g. `https://radicale.example.com`) |
| `RADICALE_USERNAME` | Radicale username |
| `RADICALE_PASSWORD` | Radicale password |

All three can be overridden via constructor arguments when
instantiating `CalendarAgent`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and
contribution guidelines. Project documentation lives under `docs/`.
