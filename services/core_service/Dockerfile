# Stage 1: Build environment
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs/ ./libs/
COPY services/core_service/ ./services/core_service/
# Ensure only core_service dependencies are resolved if possible, 
# but uv sync root is safer for workspace consistency.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Stage 2: Runtime
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
# Copy the synchronized environment and code
COPY --from=builder /app/.venv /app/.venv
COPY libs/ /app/libs/
COPY services/core_service/app /app/services/core_service/app
COPY static/ /app/static/
COPY templates/ /app/templates/

# Ensure 'uv' uses the pre-built environment
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/services/core_service/app
CMD ["uv", "run", "python", "main.py"]
