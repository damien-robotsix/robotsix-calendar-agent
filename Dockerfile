# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

# git is required: robotsix-agent-comm and robotsix-llmio are git dependencies
# that uv fetches at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifests and source, then install (no dev deps).
# README.md is required by the hatchling build backend (project readme).
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

# Run brokered by default; the Compose file can override this.
ENV CALENDAR_AGENT_TRANSPORT=brokered

# Make the installed console-script available on PATH.
ENV PATH="/app/.venv/bin:${PATH}"

CMD ["calendar-agent"]
