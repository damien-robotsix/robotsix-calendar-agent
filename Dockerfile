# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests and source, then install (no dev deps).
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev

# Run brokered by default; the Compose file can override this.
ENV CALENDAR_AGENT_TRANSPORT=brokered

# Make the installed console-script available on PATH.
ENV PATH="/app/.venv/bin:${PATH}"

CMD ["calendar-agent"]
