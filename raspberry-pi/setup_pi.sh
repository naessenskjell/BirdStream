#!/bin/bash
# Setup script for running BirdStream natively on Raspberry Pi (no Docker)
# Run as a user with sudo privileges (e.g., pi)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$REPO_DIR/venv"
PYTHON=$(which python3 || true)
if [ -z "$PYTHON" ]; then
  echo "python3 not found; install Python 3 first" >&2
  exit 1
fi

echo "Repository directory: $REPO_DIR"

echo "Updating apt and installing required packages (may ask for sudo)..."
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip ffmpeg libjpeg-dev libopenjp2-7 libtiff6 libwebp7 libavcodec-extra libcap-dev portaudio19-dev --no-install-recommends
# Ensure libcamera tools and rpicam are installed on host (optional but recommended)
sudo apt-get install -y libcamera-apps rpicam-apps || true

# Create virtualenv
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv in $VENV_DIR"
  python3 -m venv "$VENV_DIR" --system-site-packages
fi

echo "Activating venv and installing Python dependencies"
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
if [ -f "$REPO_DIR/requirements.txt" ]; then
  pip install --no-cache-dir -r "$REPO_DIR/requirements.txt"
else
  echo "requirements.txt not found in $REPO_DIR" >&2
fi

# Install ALSA default config (asound.conf) from repository if present
ASOUND_TEMPLATE="$REPO_DIR/asound.conf"
if [ -f "$ASOUND_TEMPLATE" ]; then
  echo "Installing ALSA default configuration from $ASOUND_TEMPLATE"
  TIMESTAMP=$(date +%s)
  if [ -f /etc/asound.conf ]; then
    echo "Backing up existing /etc/asound.conf to /etc/asound.conf.bak.$TIMESTAMP"
    sudo cp /etc/asound.conf /etc/asound.conf.bak.$TIMESTAMP
  fi
  sudo cp "$ASOUND_TEMPLATE" /etc/asound.conf
  sudo chown root:root /etc/asound.conf
  sudo chmod 644 /etc/asound.conf
  echo "Installed /etc/asound.conf. You may need to reboot for ALSA clients to pick up the change."
else
  echo "No asound.conf template found at $ASOUND_TEMPLATE; skipping ALSA config."
fi

echo "Setup complete. To start the service manually:"
echo "  source $VENV_DIR/bin/activate && python $REPO_DIR/main.py"
echo "Or install the systemd service described in DEPLOY_PI.md"
