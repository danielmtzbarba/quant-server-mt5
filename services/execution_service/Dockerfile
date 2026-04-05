FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Copy root configuration
COPY pyproject.toml uv.lock ./
# Copy libraries and services to satisfy workspace requirements
COPY libs/ ./libs/
COPY services/ ./services/
COPY static/ ./static/
COPY templates/ ./templates/

# Install the entire workspace dependencies
RUN uv sync --frozen --no-dev

WORKDIR /app/services/execution_service/app
CMD ["uv", "run", "python", "main.py"]
