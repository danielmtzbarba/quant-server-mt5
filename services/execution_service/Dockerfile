# Inherit from the shared Parent (already has .venv, libs, and templates pre-baked)
FROM ghcr.io/danielmtzbarba/quant-server-mt5-base:latest

# Set up the service-specific app directory
WORKDIR /app
COPY services/execution_service/app /app/services/execution_service/app

# The .venv is already in the PATH from the base image
WORKDIR /app/services/execution_service/app
CMD ["python", "main.py"]
