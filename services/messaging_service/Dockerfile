# Stage 1: Build environment
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs/ ./libs/
COPY services/messaging_service/ ./services/messaging_service/
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
# Copy the synchronized environment and code
COPY --from=builder /app/.venv /app/.venv
COPY libs/ /app/libs/
COPY services/messaging_service/app /app/services/messaging_service/app

# Ensure 'uv' uses the pre-built environment
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/services/messaging_service/app
CMD ["uv", "run", "python", "main.py"]
