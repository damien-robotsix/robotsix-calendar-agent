# syntax=docker/dockerfile:1

# Builder stage: installs build dependencies and creates the virtualenv.
FROM python:3.14-slim-bookworm AS builder

# Install uv from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /bin/

# git is required: robotsix-llmio is a git dependency that uv fetches at build time.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y --no-install-recommends git=1:2.39.5-0+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optimize uv for Docker builds.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# First layer: install only dependencies (cached unless pyproject.toml/uv.lock change).
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Second layer: copy source and install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Runtime stage: minimal image with only the virtualenv and source.
FROM python:3.14-slim-bookworm AS runtime

# Create a dedicated non-root user.
RUN groupadd -g 1001 app && useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

# Copy the virtualenv, source, and healthcheck from the builder.
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src


# Runtime configuration.
ENV PATH="/app/.venv/bin:${PATH}"

USER app

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD calendar-agent-healthcheck

CMD ["calendar-agent"]
