#!/bin/bash
set -e

# Cleanup any leftover X11 locks from previous runs
rm -f /tmp/.X0-lock
rm -rf /tmp/.X11-unix

echo "Starting X Virtual Framebuffer (Xvfb)..."
Xvfb :0 -screen 0 1280x1024x24 &
sleep 2

echo "Starting X11VNC for graphical debugging (Port 5900)..."
x11vnc -display :0 -bg -forever -nopw -quiet -listen 0.0.0.0 -xkb

echo "Neutralizing legacy Expert Advisors (EAs) to prevent automated order loops..."
rm -rf "/root/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"*

echo "Starting FastAPI Windows Server as a module inside Wine..."
wine /root/.wine/drive_c/python/python.exe -m services.mt5_service.app.main
