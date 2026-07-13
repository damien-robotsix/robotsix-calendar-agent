# Contributing to robotsix-calendar-agent

Thanks for your interest in contributing! This document covers the
development setup and the conventions this repository follows.

## Development setup

This project uses [`uv`](https://docs.astral.sh/uv/) for dependency and
environment management, and targets Python 3.14+.

```bash
git clone https://github.com/damien-robotsix/robotsix-calendar-agent.git
cd robotsix-calendar-agent
uv sync
```

The lockfile (`uv.lock`) is committed to the repository, and CI installs
dependencies with `uv sync --frozen`. When you change dependencies in
`pyproject.toml`, regenerate the lockfile with `uv lock` and commit the
result. **Never hand-edit `uv.lock`.**

Note that this repository is **not** stdlib-only — it requires runtime
dependencies (`robotsix-llmio`, `caldav`) declared
in `pyproject.toml`.

## Checks

Run the full set of checks locally before opening a pull request.
Use `make` (run `make help` for all available targets):

```bash
make lint      # lint and format check
make typecheck # static type checking (strict)
make test      # fast tests (non-integration)
make all       # run all checks
```

`make format` rewrites files to the canonical format.

## Branches and pull requests

- Create a feature branch off `main` for your change.
- Keep changes focused and accompanied by tests where applicable.
- Ensure all checks above pass before requesting review.
- Open a pull request against `main`; CI runs the same checks.
