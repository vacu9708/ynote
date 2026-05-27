#!/usr/bin/env bash
set -euo pipefail

WRAPPER="/usr/local/bin/ynote"
USER_ICON="$HOME/.local/share/icons/hicolor/256x256/apps/ynote.png"
USER_DESKTOP="$HOME/.local/share/applications/ynote.desktop"
SYSTEM_DESKTOP="/usr/share/applications/ynote.desktop"
AUTOSTART_DESKTOP="$HOME/.config/autostart/ynote.desktop"
REMOVE_DEB=0

usage() {
    cat <<EOF
Usage: ./uninstall.sh [--deb]

Removes files created by ./install.sh.

Options:
  --deb     also remove the Debian package with apt
  --help    show this help
EOF
}

case "${1:-}" in
    "")
        ;;
    --deb)
        REMOVE_DEB=1
        ;;
    --help|-h)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

echo "=== Ynote uninstaller ==="

# 1. Stop running instances, if any
if pgrep -f '[p]ython3 .*ynote.py' >/dev/null 2>&1; then
    echo "Stopping running Ynote instance(s)..."
    pkill -f '[p]ython3 .*ynote.py' || true
fi

# 2. Remove launcher wrapper
if [ -e "$WRAPPER" ]; then
    echo "Removing launcher: $WRAPPER"
    sudo rm -f "$WRAPPER"
fi

# 3. Remove desktop launcher entries
if [ -e "$USER_DESKTOP" ]; then
    echo "Removing user desktop entry: $USER_DESKTOP"
    rm -f "$USER_DESKTOP"
fi

if [ -e "$SYSTEM_DESKTOP" ]; then
    if dpkg-query -S "$SYSTEM_DESKTOP" 2>/dev/null | grep -q '^ynote:'; then
        echo "Leaving package-owned system desktop entry: $SYSTEM_DESKTOP"
        if grep -q '^Exec=/usr/local/bin/ynote' "$SYSTEM_DESKTOP" 2>/dev/null; then
            echo "Package desktop entry points to the old source launcher."
            echo "Repair it with: sudo apt install --reinstall ./dist/ynote_1.4.1.deb"
        fi
    else
        echo "Removing system desktop entry: $SYSTEM_DESKTOP"
        sudo rm -f "$SYSTEM_DESKTOP"
    fi
fi

# 4. Remove autostart entry
if [ -e "$AUTOSTART_DESKTOP" ]; then
    echo "Removing autostart entry: $AUTOSTART_DESKTOP"
    rm -f "$AUTOSTART_DESKTOP"
fi

# 5. Remove installed icon
if [ -e "$USER_ICON" ]; then
    echo "Removing installed icon: $USER_ICON"
    rm -f "$USER_ICON"
fi

# 6. Refresh caches
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true

if [ "$REMOVE_DEB" -eq 1 ]; then
    echo "Removing Debian package: ynote"
    sudo apt-get remove -y ynote
fi

echo ""
echo "Done! Ynote has been uninstalled."
echo "The source files and any note data have not been deleted."
echo "System packages installed as dependencies have also been kept."
