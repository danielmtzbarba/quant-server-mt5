#!/bin/bash
# -----------------------------------------------------------------------------
# Setup Local Quality Guard (Pre-Push Hook)
# -----------------------------------------------------------------------------
set -e

echo "🛡️  Configuring Local Quality Guard..."

# 1. Ensure pre-commit is installed (via uv)
if ! command -v pre-commit &> /dev/null; then
  echo "Installing pre-commit tool..."
  uv tool install pre-commit
fi

# 2. Install hooks into the local .git directory
echo "Installing pre-push hooks... (This stops broken pushes)"
uv tool run pre-commit install --hook-type pre-push

# 3. Success Verification
echo "✅  Quality Guard Active!"
echo "Your code will now be checked for 'ruff' and 'pytest' on every 'git push'."
