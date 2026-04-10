# --- Master Base Image Architecture ---
# This image is built once and shared across all microservices (Core, Execution, Messaging).
# It centralizes all heavy extractions and installations, reducing deployment time by ~60%.

# Stage 1: Build environment (The Heavy Lifter)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# 1. Install all dependencies into a shared .venv
# We copy the root configuration and all shared libraries.
COPY pyproject.toml uv.lock ./
COPY libs/ ./libs/
COPY templates/ ./templates/

# Run the 200MB+ installation step once.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync  --no-dev

# Stage 2: Optimized Runtime Base (The Child Parent)
# This is the image that your microservices will actually use as their base.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
WORKDIR /app

# Copy the initialized environment and shared assets.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/libs /app/libs
COPY --from=builder /app/templates /app/templates

# Ensure all inheriting services use the pre-built environment automatically.
ENV PATH="/app/.venv/bin:$PATH"
