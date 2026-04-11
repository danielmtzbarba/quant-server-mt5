# Inherit from the shared Parent (already has .venv, libs, and templates pre-baked)
ARG GITHUB_REPOSITORY_OWNER=danielmtzbarba
FROM ghcr.io/${GITHUB_REPOSITORY_OWNER}/quant-server-mt5-base:latest
LABEL org.opencontainers.image.source=https://github.com/danielmtzbarba/quant-server-mt5

# Set up the service-specific app directory
WORKDIR /app
COPY services/sync_service/app /app/services/sync_service/app
COPY static/ /app/static/
COPY templates/ /app/templates/

# The .venv is already in the PATH from the base image
WORKDIR /app
CMD ["python", "-m", "services.sync_service.app.main"]
