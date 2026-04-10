# Inherit from the shared Parent (already has .venv, libs, and templates pre-baked)
FROM ghcr.io/danielmtzbarba/quant-server-mt5-base:latest

# Set up the service-specific app directory
WORKDIR /app
COPY services/sync_service/app /app/services/sync_service/app
COPY static/ /app/static/
COPY templates/ /app/templates/

# The .venv is already in the PATH from the base image
WORKDIR /app/services/sync_service/app
CMD ["python", "main.py"]
