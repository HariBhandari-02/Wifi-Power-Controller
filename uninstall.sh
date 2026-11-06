#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Remove Wi-Fi Power Controller for the current user.
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
RULE_DEST="/etc/polkit-1/rules.d/50-wifi-power-toggle.rules"

rm -f "$BIN_DIR/wifi-power-toggle.py" \
      "$APP_DIR/wifi-power-controller.desktop" \
      "$ICON_DIR/wifi-power-controller.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" || true
fi

if [ -e "$RULE_DEST" ]; then
    echo "Removing Polkit rule $RULE_DEST (sudo required)..."
    sudo rm -f "$RULE_DEST"
fi

echo "Wi-Fi Power Controller removed."
