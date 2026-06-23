# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial scaffold: calendar/contacts agent with agent-comm + llmio.

### Fixed

- Pre-commit CI failures: bandit B101 (assert), B105 (token variable name),
  mypy untyped-decorator on pydantic field validators, and detect-secrets false
  positives on workflow commit SHAs and test strings.
