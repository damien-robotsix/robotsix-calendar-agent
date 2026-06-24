# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Added `workflow-audit` CI job that runs zizmor to audit workflow files for security anti-patterns, with SARIF output uploaded to the Security tab.
- Pinned `actions/checkout` and `actions/dependency-review-action` in the `dependency-review` job to immutable SHAs (fixes a pre-existing zizmor finding).

- Enable Ruff's `RUF` rule set and remove three stale `# noqa: BLE001` suppressions.

- Initial scaffold: calendar/contacts agent with agent-comm + llmio.
- Pre-commit CI workflow (`pre-commit-ci.yml`) to enforce hooks in CI.

### Fixed

- `_entity_op` no longer silently creates an entity when the LLM omits the
  `uid` key from an update operation's params. The operation type is now
  threaded through the dispatch layer to detect update intents and require a
  non-empty `uid`.
- Pre-commit CI failures: bandit B101 (assert), B105 (token variable name),
  mypy untyped-decorator on pydantic field validators, and detect-secrets false
  positives on workflow commit SHAs and test strings.
