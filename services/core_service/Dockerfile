# Inherit from the shared Parent (already has .venv, libs, and templates pre-baked)
FROM ghcr.io/danielmtzbarba/quant-base:latest

# Set up the service-specific app directory
WORKDIR /app
COPY services/core_service/app /app/services/core_service/app
COPY static/ /app/static/

# The .venv is already in the PATH from the base image
WORKDIR /app/services/core_service/app
CMD ["python", "main.py"]
