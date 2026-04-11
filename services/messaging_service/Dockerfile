# Inherit from the shared Parent (already has .venv, libs, and templates pre-baked)
FROM ghcr.io/danielmtzbarba/quant-server-mt5-base:latest

# Set up the service-specific app directory
WORKDIR /app
COPY services/messaging_service/app /app/services/messaging_service/app

# The .venv is already in the PATH from the base image
WORKDIR /app
CMD ["python", "-m", "services.messaging_service.app.main"]
