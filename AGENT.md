# robotsix-calendar-agent — agent guidance

This repo follows the [robotsix stack standards](https://github.com/damien-robotsix/robotsix-standards).

## Scope & design

**Stateless agent** that brokers natural-language calendar/contact
instructions to a Radicale CalDAV/CardDAV server. Entry points:

| Entry point | Module | Description |
|---|---|---|
| Long-lived in-process service | `entrypoint.main` | Blocks until SIGTERM/SIGINT |
| In-process agent | `agent.CalendarAgent` | Constructs its own in-process `Agent` (used in tests / single-process mode) |

**No local data persistence** — there is no `data_dir_audit` and no
filesystem state. All state lives in the Radicale server.

**LLM operations always go through `robotsix_llmio`** — never call
provider SDKs directly. Intent parsing (`intent_parser.IntentParser`)
uses llmio with the `openrouter-deepseek` provider extra. Tracing
requires the `tracing` extra (see Tracing below).

## Configuration conventions

All configuration lives in **12 `pydantic_settings.BaseSettings` fields**
in `src/robotsix_calendar_agent/settings.py`. Every field is documented
in `docs/configuration.md` with its type, default, and description.

**Rule:** When you add, remove, or change a `BaseSettings` field in
`settings.py`, update `docs/configuration.md` in the same change.
The `env_doc_sync` periodic workflow enforces this automatically —
it compares the settings fields against the docs table and blocks
merges that drift.

**Settings loaded at import/construction time** — `Settings()` is
instantiated inside `CalendarAgent.__init__` and `main()`, not at module
level. Tests use the `clean_env` autouse fixture (`tests/conftest.py`)
to prevent env-var leakage.

## Testing conventions

**Tests never touch the network.** Every external dependency is mocked:

| Dependency | Mock seam | How tests inject it |
|---|---|---|
| CalDAV library (`caldav`) | `sys.modules["caldav"]` | `tests/caldav_client/test_caldav_client.py` — `reset_mock_caldav` autouse fixture swaps in a `MagicMock` |
| LLM (`robotsix_llmio`) | `unittest.mock.patch` on `IntentParser` | `tests/conftest.py` — `calendar_agent` fixture patches `IntentParser` with `autospec=True` |
**Test layout mirrors source modules** — one test directory per source
module under `tests/` (e.g. `tests/agent/`, `tests/caldav_client/`).
Shared fixtures live in `tests/conftest.py`.

**Integration test**: `tests/caldav_client/test_caldav_integration.py`
uses a session-scoped `caldav_client` fixture from
`tests/caldav_client/caldav_test_server.py`. This fixture spins up a
real Radicale container via docker-compose and is the only test that
touches a live CalDAV server — it is skipped in CI unless a Radicale
service is available.

## Tracing

Langfuse tracing is initialised at **module level** on `CalendarAgent`
import (`src/robotsix_calendar_agent/agent.py`):

```python
from robotsix_llmio.core import setup_langfuse_tracing
setup_langfuse_tracing()
```

This means importing `CalendarAgent` (or any module that imports it)
activates OpenTelemetry/OTLP export. The `robotsix-llmio[tracing]`
extra provides the required OTLP dependencies.

Two periodic workflows operate on tracing data:

- **`langfuse_cleanup`** — prunes stale trace sessions.
- **`trace_review`** — surfaces anomalous traces for human review.

Both are active and must not be disabled without coordination.

## Module layout

```
src/robotsix_calendar_agent/
├── __init__.py
├── agent.py                    # CalendarAgent — wires everything together
├── add_to_calendar_handler.py  # Structured handler for auto-mail "add_to_calendar" payloads
├── entrypoint.py               # main() — long-lived in-process service
├── caldav_client.py            # CalDavClient — typed CalDAV/CardDAV wrapper with tenacity retries
├── intent_parser.py            # IntentParser — llmio-based NL → ParsedIntent
├── py.typed                    # PEP 561 marker
└── settings.py                 # BaseSettings — single source of truth for env vars
```

## Dependencies


- **`robotsix-llmio[openrouter-deepseek,tracing]`** — LLM intent parsing + Langfuse OTLP export
- **`caldav`** — CalDAV/CardDAV client library
- **`pydantic` / `pydantic-settings`** — configuration & data models
- **`tenacity>=9.0`** — retry decorators on CalDAV operations

## Periodic workflows

This repo is targeted by **15 periodic agent workflows** (second-highest
in the fleet). Key ones referenced above:

- `env_doc_sync` — enforces `docs/configuration.md` ↔ `settings.py` consistency
- `langfuse_cleanup` — prunes stale Langfuse trace sessions
- `trace_review` — surfaces anomalous traces

When making changes, consider whether any periodic workflow's
expectations would be violated (e.g. changing a `BaseSettings` field
without updating `docs/configuration.md` will cause `env_doc_sync` to
flag the PR).
