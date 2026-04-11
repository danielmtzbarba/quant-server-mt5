#!/bin/bash
set -e

echo "--- Environment Audit ---"
# Check InfluxDB Config
for var in INFLUX_URL INFLUX_TOKEN INFLUX_ORG INFLUX_BUCKET; do
  if [ -z "${!var}" ]; then
    echo "✖ $var is MISSING"
  else
    if [[ "$var" == *"TOKEN"* ]]; then
        echo "✓ $var is present"
    else
        echo "✓ $var is set to ${!var}"
    fi
  fi
done

# Check MT5 Connectivity
echo "✓ MT5_SERVICE_URL: ${MT5_SERVICE_URL:-"http://localhost:8000 (Default)"}"
echo "--------------------------"

echo "Starting Sync & Dashboard Service..."
python -m services.sync_service.app.main
