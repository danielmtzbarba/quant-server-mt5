# Lean MT5 Service Dockerfile
# Inherits from the Master Wine Base to ensure fast builds.

ARG GITHUB_REPOSITORY_OWNER=danielmtzbarba
FROM ghcr.io/${GITHUB_REPOSITORY_OWNER}/quant-server-mt5-wine-base:latest

LABEL org.opencontainers.image.source=https://github.com/danielmtzbarba/quant-server-mt5

# 1. Pull the pre-installed MT5 portable archive from GitHub Releases
RUN wget -qO /tmp/mt5.tar.gz "https://github.com/danielmtzbarba/quant-server-mt5/releases/download/v0.1.0-alpha/mt5.tar.gz"

# 2. Unzip them directly into the Wine C: drive
RUN mkdir -p "/root/.wine/drive_c/Program Files/" && \
    tar -xzf /tmp/mt5.tar.gz -C "/root/.wine/drive_c/Program Files/" && \
    rm /tmp/mt5.tar.gz

# 3. Copy and Install shared libs
WORKDIR /app
COPY libs /app/libs
RUN xvfb-run -a wine /root/.wine/drive_c/python/python.exe -m pip install \
    /app/libs/common_config /app/libs/common_logging

# 4. Copy Application context (ensure full package path for Python -m)
COPY services/__init__.py /app/services/__init__.py
COPY services/mt5_service /app/services/mt5_service
RUN touch /app/services/__init__.py /app/services/mt5_service/__init__.py
COPY services/mt5_service/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000 5900

ENTRYPOINT ["/app/entrypoint.sh"]
