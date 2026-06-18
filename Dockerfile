# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm@sha256:88fcf3024d2744b4af3698b5c60ca9e506f376c5e94c3c1ab4a6a423706545ed

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

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
