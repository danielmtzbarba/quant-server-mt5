FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV WINEPREFIX=/root/.wine
ENV WINEARCH=win64
ENV DISPLAY=:0
ENV PYTHONHASHSEED=0

# 1. Install prerequisites (Wine, Xvfb, x11vnc, unzip, winetricks)
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wine wine64 wine32 xauth xvfb wget x11vnc software-properties-common winbind unzip ca-certificates winetricks && \
    rm -rf /var/lib/apt/lists/*


# 2. Initialize Wine and install VC Redist
RUN xvfb-run -a wineboot -u && \
    xvfb-run -a winetricks -q vcrun2015

# 3. Install Python via Embeddable Zip
WORKDIR /root/.wine/drive_c/python
RUN wget -q https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip && \
    unzip python-3.8.10-embed-amd64.zip && \
    rm python-3.8.10-embed-amd64.zip

# 4. Fix Python path to enable site-packages
RUN sed -i 's/#import site/import site/g' python38._pth

# 5. Install Pip
RUN wget -q https://bootstrap.pypa.io/pip/3.8/get-pip.py && \
    xvfb-run -a wine /root/.wine/drive_c/python/python.exe get-pip.py && \
    rm get-pip.py

# 6. Install MT5 + FastAPI + httpx
RUN xvfb-run -a wine /root/.wine/drive_c/python/python.exe -m pip install MetaTrader5 fastapi uvicorn httpx


# 7. Pull the pre-installed MT5 portable archive from GitHub Releases
RUN wget -qO /tmp/mt5.tar.gz "https://github.com/danielmtzbarba/quant-server-mt5/releases/download/v0.1.0-alpha/mt5.tar.gz"

# 8. Unzip them directly into the Wine C: drive
RUN mkdir -p "/root/.wine/drive_c/Program Files/" && \
    tar -xzf /tmp/mt5.tar.gz -C "/root/.wine/drive_c/Program Files/" && \
    rm /tmp/mt5.tar.gz

# 9. Copy Application layers
WORKDIR /app
COPY app /app/app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000 5900

ENTRYPOINT ["/app/entrypoint.sh"]
