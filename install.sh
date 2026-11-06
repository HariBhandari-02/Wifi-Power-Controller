#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Install Wi-Fi Power Controller for the current user.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
RULE_DEST="/etc/polkit-1/rules.d/50-wifi-power-toggle.rules"

WITH_POLKIT=0

usage() {
    cat <<USAGE
Usage: ./install.sh [--with-polkit] [-h|--help]

  --with-polkit  Also install a Polkit rule so admin-group users can toggle
                 power saving without a password prompt (needs sudo once).
USAGE
}

for arg in "$@"; do
    case "$arg" in
        --with-polkit) WITH_POLKIT=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

distro_hint() {
    local id="" id_like=""
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        id="$(. /etc/os-release && echo "${ID:-}")"
        # shellcheck disable=SC1091
        id_like="$(. /etc/os-release && echo "${ID_LIKE:-}")"
    fi
    case " $id $id_like " in
        *" debian "*|*" ubuntu "*) echo "sudo apt install python3 python3-tk iw policykit-1" ;;
        *" fedora "*|*" rhel "*)   echo "sudo dnf install python3 python3-tkinter iw polkit" ;;
        *" arch "*)                echo "sudo pacman -S python tk iw polkit" ;;
        *" suse "*)                echo "sudo zypper install python3 python3-tk iw polkit" ;;
        *)                         echo "install python3, tkinter, iw and polkit (pkexec) with your package manager" ;;
    esac
}

find_tool() {
    # Look in PATH, then the sbin dirs that are often missing from user PATHs.
    PATH="$PATH:/usr/sbin:/sbin" command -v "$1" 2>/dev/null || true
}

missing=()
command -v python3 >/dev/null 2>&1 || missing+=("python3")
if command -v python3 >/dev/null 2>&1 && ! python3 -c "import tkinter" >/dev/null 2>&1; then
    missing+=("tkinter (python3-tk)")
fi
IW_PATH="$(find_tool iw)"
[ -n "$IW_PATH" ] || missing+=("iw")
[ -n "$(find_tool pkexec)" ] || missing+=("pkexec (polkit)")

if [ "${#missing[@]}" -gt 0 ]; then
    echo "Missing requirements: ${missing[*]}" >&2
    echo "Try: $(distro_hint)" >&2
    exit 1
fi

echo "Installing for user $USER..."
mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

install -m 755 "$SRC_DIR/wifi-power-toggle.py" "$BIN_DIR/wifi-power-toggle.py"
sed "s|@HOME@|$HOME|g" "$SRC_DIR/data/wifi-power-controller.desktop.in" \
    > "$APP_DIR/wifi-power-controller.desktop"
chmod 644 "$APP_DIR/wifi-power-controller.desktop"
install -m 644 "$SRC_DIR/data/wifi-power-controller.svg" "$ICON_DIR/wifi-power-controller.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" || true
fi

if [ "$WITH_POLKIT" -eq 1 ]; then
    if getent group sudo >/dev/null 2>&1; then
        ADMIN_GROUP=sudo
    elif getent group wheel >/dev/null 2>&1; then
        ADMIN_GROUP=wheel
    else
        echo "Could not find a 'sudo' or 'wheel' group; skipping Polkit rule." >&2
        exit 1
    fi
    # pkexec reports the canonical program path to Polkit.
    IW_REAL="$(readlink -f "$IW_PATH")"
    TMP_RULE="$(mktemp)"
    trap 'rm -f "$TMP_RULE"' EXIT
    sed -e "s|@GROUP@|$ADMIN_GROUP|g" -e "s|@IW@|$IW_REAL|g" \
        "$SRC_DIR/data/50-wifi-power-toggle.rules.in" > "$TMP_RULE"
    echo "Installing Polkit rule to $RULE_DEST (group: $ADMIN_GROUP, sudo required)..."
    sudo install -m 644 -o root -g root "$TMP_RULE" "$RULE_DEST"
fi

echo "Done. Launch 'Wi-Fi Power Controller' from your app menu, or run:"
echo "  $BIN_DIR/wifi-power-toggle.py"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Note: $BIN_DIR is not on your PATH." ;;
esac
if [ "$WITH_POLKIT" -ne 1 ]; then
    echo "Toggling will ask for your password. Re-run with --with-polkit to skip the prompt."
fi
