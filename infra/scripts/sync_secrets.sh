#!/bin/bash
# Helper script to sync local .env files to GitHub Secrets using gh cli

set -e

# Colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed.${NC}"
    echo "Please visit: https://cli.github.com/"
    exit 1
fi

echo "--- Syncing GitHub Secrets ---"

# 1. Individual MT5 Service Variables (from dedicated env file)
if [ -f "infra/envs/mt5.env" ]; then
    echo "Updating MT5 Service Secrets from infra/envs/mt5.env..."
    gh secret set --env-file infra/envs/mt5.env
    echo -e "${GREEN}✓ MT5 Service secrets updated.${NC}"
else
    echo "Skipping MT5 Service Secrets (file not found: infra/envs/mt5.env)"
fi

# 2. Azure Environment Block (The massive .env file used by CD)
if [ -f "infra/envs/azure_full.env" ]; then
    echo "Updating AZURE_ENV bundle from infra/envs/azure_full.env..."
    gh secret set AZURE_ENV < infra/envs/azure_full.env
    echo -e "${GREEN}✓ AZURE_ENV secret updated.${NC}"
fi

echo -e "\n${GREEN}Done! GitHub Secrets are now in sync with your local configurations.${NC}"
