#!/bin/bash
# Helper to run BirdStream natively on the Pi. Activates venv and runs main.py
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "Virtualenv not found. Run setup_pi.sh first." >&2
  exit 1
fi

# Activate the virtualenv
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Export recommended environment variables
export BIRDSTREAM_CONFIG="$REPO_DIR/config.yaml"

# Run the main application
python "$REPO_DIR/src/main.py" "$@"
