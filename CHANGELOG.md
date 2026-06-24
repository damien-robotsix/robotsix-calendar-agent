# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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
- `deps-bump.yml` reusable workflow adoption for automated dependency bumps.
- `env_doc_sync` periodic workflow enabled to enforce `settings.py` ↔
  `docs/configuration.md` consistency.

### Changed

- Dockerfile hardened with multi-stage build, non-root user, BuildKit cache
  mounts, and UV optimizations.
- `docker-publish.yml` migrated to consume mill's reusable `docker-release.yml`.
- All GitHub Actions and reusable workflow references pinned to immutable
  SHA digests.
- `docker-release.yml` reusable workflow reference pinned to SHA digest in
  `docker-publish.yml`.
- Decomposed 140-line `handle_add_to_calendar` function into smaller, focused
  phases: `_parse_email_payload`, `_extract_json_payload`,
  `_parse_and_validate_event`, `_apply_defaults`, and `_register_handlers`.
- DRY duplicate delete handler functions via a single `_delete_entity_op`
  helper shared by `_handle_delete_event` and `_handle_delete_contact`.
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

### Fixed

- `_entity_op` no longer silently creates an entity when the LLM omits the
  `uid` key from an update operation's params. The operation type is now
  threaded through the dispatch layer to detect update intents and require a
  non-empty `uid`.
- Pre-commit CI failures: bandit B101 (assert), B105 (token variable name),
  mypy untyped-decorator on pydantic field validators, and detect-secrets false
  positives on workflow commit SHAs and test strings.
- `_IntentOutput.operation` changed from `str` to `Literal["create", "update",
  "delete", "list"]` to strengthen structured-output enum constraints.
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
- Agent responses now emit a human-readable `reply` alongside the structured
  `result`.
- Docker build: stale Python base-image digest pin fixed.
- `vobject` installed so CalDAV read-back works correctly.
- Intent parser corrected to use the llmio agent API with the non-reasoning
  tier.
- CalDAV operations emit valid iCalendar datetimes; llmio provider extra
  installed.
