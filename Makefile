.DEFAULT_GOAL := all

.PHONY: all
all: lint typecheck test  ## Run all checks (default goal)

.PHONY: install
install: .venv  ## Install dev environment and pre-commit hooks
	uv sync --frozen --group dev
	pre-commit install

.venv:
	uv venv

.PHONY: lint
lint: .venv  ## Run linter and format check
	uv run ruff check src/
	uv run ruff format --check src/

.PHONY: format
format: .venv  ## Auto-format source code
	uv run ruff check --fix src/
	uv run ruff format src/

.PHONY: typecheck
typecheck: .venv  ## Run mypy static type checker
	uv run mypy src/

.PHONY: test
test: .venv  ## Run tests (non-integration)
	uv run pytest -m 'not integration' tests/

.PHONY: clean
clean:  ## Remove caches and build artifacts
	rm -rf __pycache__ .pytest_cache .ruff_cache htmlcov build dist *.egg-info

.PHONY: help
help:  ## Display this help message
	@grep -E '^.PHONY: .*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ".PHONY: |## "}; {printf "\033[36m%-19s\033[0m %s\n", $$2, $$3}'
