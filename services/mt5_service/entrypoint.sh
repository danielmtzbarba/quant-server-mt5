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

echo "--- Runtime Diagnostics ---"
echo "Working Directory: $(pwd)"
echo "Listing /app/services:"
ls -F /app/services/ || echo "Failed to list /app/services"
echo "Wine View (Z:\\app\\services):"
wine cmd /c "dir Z:\\app\\services" || echo "Wine failed to see Z:\\app\\services"
echo "---------------------------"

echo "--- Environment Audit ---"
for var in MT5_USER MT5_PASSWORD MT5_SERVER; do
  if [ -z "${!var}" ]; then
    echo "✖ $var is MISSING"
  else
    echo "✓ $var is present"
  fi
done
echo "--------------------------"

echo "Neutralizing legacy Expert Advisors (EAs) to prevent automated order loops..."
rm -rf "/root/.wine/drive_c/Program Files/MetaTrader 5/MQL5/Experts/"*

echo "Starting FastAPI Windows Server as a module inside Wine..."
# Using wine cmd /c to ensure PYTHONPATH is set in the Windows environment
wine cmd /c "set PYTHONPATH=Z:\\app && C:\\python\\python.exe -m services.mt5_service.app.main"
