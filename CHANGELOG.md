# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Removed spurious `agent` dependency from `component_agent` module entry in `docs/modules.yaml`.

### Changed
- Enabled Ruff `S` (flake8-bandit) rules in `pyproject.toml` and removed the slower `bandit` pre-commit hook.

### Added
- Docker `HEALTHCHECK` via `healthcheck.py` that validates CalDAV reachability using the existing `CalDavClient.health()` probe.
- Registered `docs/modules.yaml` under the `init` module's `doc_paths`.
- Extracted `_iter_config_fields` helper in `config_contract.py` to deduplicate settings-iteration loops across `get_config_snapshot` and `describe_config`.

### Fixed
- Fixed `intent_parser` entry in `docs/modules.yaml`: added missing `path` key, added `test_paths` key, and moved test files out of `paths` to match conventions of other module entries.
- Added missing `reference/component_agent.md` to `mkdocs.yml` navigation under Code Reference.
- `brokered_entrypoint.py`: removed unreachable `if not token:` guard in `_build_component_responder` (token-empty invariant is already enforced by `ComponentAgentSettings`). Added test coverage for the enabled-with-token path.

### Changed
- Removed dead `if TYPE_CHECKING: pass` blocks and unused `TYPE_CHECKING` imports from `agent.py` and `caldav_client.py`.
- `__init__.py`: re-exported symbols now flow through `agent.py` instead of
  duplicating imports from `.caldav_client` and `.intent_parser`.
- Merged `component_agent/responder.py` into `brokered_entrypoint.py`:
  `ComponentAgentResponder` and `COMPONENT_KINDS` now live alongside the
  brokered lifecycle, eliminating the deferred/lazy import dance between
  the two modules.
- `agent.py`: removed unused `operation` parameter from six dispatch handlers
  (`_handle_list_events`, `_handle_list_tasks`, `_handle_list_calendars`,
  `_handle_delete_event`, `_handle_list_contacts`, `_handle_delete_contact`);
  `_dispatch` now only passes `operation` to the two create/update handlers
  that forward it to `_entity_op`.
- `caldav_client.py`: lifted duplicated inner closures `_text` / `_dt` from
  `_to_calendar_event` and `_to_task` into module-level helpers `_comp_text`
  and `_comp_dt`.
- `intent_parser.py`: replaced `get_provider` + `provider.build_agent(level=2)` with `build_agent_for_level(2, ...)` to match current `robotsix-llmio` API.
- Hardened Dockerfile: pinned base images to digest, added uv package cache
  mount, cleaned apt lists in builder stage, and replaced `RUN chown` with
  `COPY --chown` to eliminate an unnecessary layer.
- Bumped `robotsix-llmio` to include the PromptedOutput auto-wrap fix for
  reasoning tiers, preventing "Thinking mode does not support this tool_choice"

### Fixed
- Added missing `RADICALE_DEFAULT_CALENDAR` commented entry to `.env.example`.
- Fix `_entity_op` bug where a create operation with an incidental `uid` in
  params was silently dispatched as an update. The dispatch now uses only the
  `operation` string to decide between create/update.
- Component-agent responder delegation in `_handle_request_impl` now catches
  unexpected exceptions and returns an `Error` response instead of letting them
  propagate unhandled.
- Updated `_INTENT_SYSTEM_PROMPT` to instruct the LLM to omit the `uid` key
  (rather than leaving it empty) when a UID is needed but not provided — the
  handler already rejects empty UIDs, so the old prompt was misleading the model.
  errors when using `level=2` with raw pydantic `output_type`.

### Added
- Added `COMPONENT_AGENT_ENABLED`, `COMPONENT_AGENT_TOKEN`, and
  `COMPONENT_AGENT_ID` commented entries to `.env.example` for discoverability.

- Added `list_tasks` operation: the calendar agent can now list VTODO tasks
  from a CalDAV calendar via a new `Task` dataclass, `CalDavClient.list_tasks()`,
  and `list_tasks` intent classifier support. Fixes broken `query_tasks` channel
  that was incorrectly routing to the CardDAV contacts API.

- Added `workflow-audit` CI job that runs zizmor to audit workflow files for security anti-patterns, with SARIF output uploaded to the Security tab.
- Pinned `actions/checkout` and `actions/dependency-review-action` in the `dependency-review` job to immutable SHAs (fixes a pre-existing zizmor finding).

- Enable Ruff's `RUF` rule set and remove three stale `# noqa: BLE001` suppressions.
- Added `fail_under = 85` to `[tool.coverage.report]` in `pyproject.toml` so local `pytest --cov` runs enforce the same 85% coverage threshold as CI.

- Expand `SECURITY.md` with supported versions table and disclosure policy.

- Initial scaffold: calendar/contacts agent with agent-comm + llmio.
- Pre-commit CI workflow (`pre-commit-ci.yml`) to enforce hooks in CI.
- Langfuse tracing via `robotsix-llmio[tracing]` extra for OpenTelemetry export.
- Dependency-review-action in CI pipeline for supply-chain gate on PRs.
- Auto-generated API reference documentation for all public modules.
- `docs/configuration.md` documenting all 12 `BaseSettings` environment variables.
- Tenacity-based retry logic (`tenacity>=9.0`) to `CalDavClient` for transient
  network failures on CalDAV/CardDAV operations.
- `AGENT.md` with repo-specific agent conventions for mill workflows.
- Unit tests for `settings.py` (`tests/test_settings.py`).
- `env_doc_sync` periodic workflow enabled to enforce `settings.py` ↔
  `docs/configuration.md` consistency.

### Changed

- Dockerfile hardened with multi-stage build, non-root user, BuildKit cache
  mounts, and UV optimizations.
- `docker-publish.yml` migrated to consume mill's reusable `docker-release.yml`.
- All GitHub Actions and reusable workflow references pinned to immutable
  SHA digests.
- Decomposed 140-line `handle_add_to_calendar` function into smaller, focused
  phases: `_parse_email_payload`, `_extract_json_payload`,
  `_parse_and_validate_event`, `_apply_defaults`, and `_register_handlers`.
- DRY duplicate delete handler functions via a single `_delete_entity_op`
  helper shared by `_handle_delete_event` and `_handle_delete_contact`.
- `_IntentOutput.operation` changed from `str` to `Literal["create", "update",
  "delete", "list"]` to strengthen structured-output enum constraints.
- Collapsed identical create/update handler wrappers into single functions
  each (`_handle_create_or_update_event`, `_handle_create_or_update_contact`).
- Refactored environment variable configuration with `pydantic-settings` for
  type-safe, centralized config management via `Settings` class.
- Reorganized `add_to_calendar_handler`, `caldav_client`, and
  `brokered_entrypoint` modules to per-module layout (src/docs/tests).
- Calendar agent now driven via the shared `BrokeredAgent` from
  `robotsix-agent-comm`.
- CalDAV read-back now uses `icalendar_instance`, dropping the `vobject`
  dependency.
- `deps-bump.yml` reusable workflow adopted for automated dependency bumps.
- Agent responses now emit a human-readable `reply` alongside the structured
  `result`.

### Fixed

- `_entity_op` no longer silently creates an entity when the LLM omits the
  `uid` key from an update operation's params. The operation type is now
  threaded through the dispatch layer to detect update intents and require a
  non-empty `uid`.
- Pre-commit CI failures: bandit B101 (assert), B105 (token variable name),
  mypy untyped-decorator on pydantic field validators, and detect-secrets false
  positives on workflow commit SHAs and test strings.
- `list_events` and `list_contacts` docstrings corrected: implementation
  searches only the first/default address book / calendar, not "all".
- `delete_event` docstring corrected: implementation raises on not-found
  (not idempotent) — docstring now matches behaviour.
- `BROKER_CLIENT_CERT` and `BROKER_CLIENT_KEY` now correctly wired into
  `_build_brokered_agent` so mTLS client certificates are actually used.
- Dispatch handlers now validate that `uid` is non-empty for update/delete
  operations (the LLM prompt previously said "leave it empty").
- `docs.yml` permissions fixed for `mkdocs gh-deploy`: `contents:write`
  instead of `contents:read`.
- Error-handling lint findings resolved across all six source modules.
- Removed unused `client` parameter from `_entity_op` in `agent.py`.
- `BROKER_PORT` default mismatch between docs and code fixed.
- Docker build: stale Python base-image digest pin fixed.
- Intent parser corrected to use the llmio agent API with the non-reasoning
  tier.
- CalDAV operations now emit valid iCalendar datetimes for recurrence rules
  and all-day events.
- `llmio` provider extra installed so the intent-parser agent can resolve
  its model provider at runtime.
