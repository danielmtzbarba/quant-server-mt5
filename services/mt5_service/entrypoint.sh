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
for var in MT5_PATH MT5_LOGIN MT5_PASSWORD MT5_SERVER; do
  if [ -z "${!var}" ]; then
    echo "✖ $var is MISSING"
  else
    if [[ "$var" == *"PATH"* || "$var" == *"SERVER"* ]]; then
        echo "✓ $var is set to ${!var}"
    else
        echo "✓ $var is present"
    fi
  fi
done
echo "--------------------------"

echo "--- Python Search Path (Wine) ---"
wine /root/.wine/drive_c/python/python.exe -c "import sys; print(sys.path)"
echo "---------------------------------"

echo "Starting FastAPI Windows Server as a module inside Wine..."
# The PYTHONPATH is now hard-wired into the Python binary's config in the base image
wine /root/.wine/drive_c/python/python.exe -m services.mt5_service.app.main
