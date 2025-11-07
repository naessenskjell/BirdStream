#!/bin/bash
# Installer to place the asound.conf template into /etc/asound.conf (backs up existing)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/asound.conf"

if [ ! -f "$TEMPLATE" ]; then
  echo "Template file not found: $TEMPLATE" >&2
  exit 1
fi

TIMESTAMP=$(date +%s)
if [ -f /etc/asound.conf ]; then
  echo "Backing up existing /etc/asound.conf to /etc/asound.conf.bak.$TIMESTAMP"
  sudo cp /etc/asound.conf /etc/asound.conf.bak.$TIMESTAMP
fi

echo "Copying template to /etc/asound.conf (requires sudo)..."
sudo cp "$TEMPLATE" /etc/asound.conf
sudo chown root:root /etc/asound.conf
sudo chmod 644 /etc/asound.conf

echo "Installed /etc/asound.conf. You may need to reboot for changes to take effect."
