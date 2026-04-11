# --- Master MT5 Wine Base Image ---
# This image contains the heavy Wine environment, VC Redist, and Python 3.8.
# It is built once and shared by mt5_service to reduce deployment time.

FROM ubuntu:22.04
LABEL org.opencontainers.image.source=https://github.com/danielmtzbarba/quant-server-mt5

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

# 4. Enable site-packages and inject application path directly into Python's search path
RUN sed -i 's/#import site/import site/g' python38._pth && \
    echo "Z:/app" > app_path.pth

# 5. Install Pip
RUN wget -q https://bootstrap.pypa.io/pip/3.8/get-pip.py && \
    xvfb-run -a wine /root/.wine/drive_c/python/python.exe get-pip.py && \
    rm get-pip.py

# 6. Install Core Python requirements for MT5
RUN xvfb-run -a wine /root/.wine/drive_c/python/python.exe -m pip install \
    MetaTrader5 fastapi uvicorn httpx rich python-dotenv pydantic-settings
