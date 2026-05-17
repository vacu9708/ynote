#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$SCRIPT_DIR/ynote.py"
ICON="$SCRIPT_DIR/icon.png"

echo "=== Ynote installer ==="

# 1. Refresh package index and install dependencies
echo "Updating package lists..."
sudo apt-get update -qq

echo "Installing system dependencies..."
sudo apt-get install -y python3-gi gir1.2-gtk-3.0

# AppIndicator3 adds a system-tray icon; app works fine without it
if sudo apt-get install -y gir1.2-appindicator3-0.1 2>/dev/null; then
    echo "AppIndicator3 installed (system tray enabled)"
else
    echo "AppIndicator3 not available — system tray skipped (right-click notes to manage)"
fi

# 2. Make the app executable
chmod +x "$APP"

# 3. Wrapper script
WRAPPER=/usr/local/bin/ynote
echo "Creating launcher at $WRAPPER..."
sudo tee "$WRAPPER" > /dev/null <<EOF
#!/usr/bin/env bash
GDK_BACKEND=x11 exec python3 "$APP" "\$@"
EOF
sudo chmod +x "$WRAPPER"

# 4. Install icon into the user hicolor theme so GNOME caches it properly.
#    Every time install.sh is re-run the icon is refreshed and the cache is
#    invalidated, so changing icon.png + re-running install.sh is all it takes.
ICON_THEME_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_THEME_DIR"
if [ -f "$ICON" ]; then
    cp -f "$ICON" "$ICON_THEME_DIR/ynote.png"
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    ICON_NAME="ynote"
    echo "Icon installed to icon theme"
else
    ICON_NAME="accessories-text-editor"
    echo "icon.png not found — using system icon"
fi

# 5. .desktop file — makes the app appear in the dock/launcher
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/ynote.desktop"
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Ynote
Comment=Sticky notes for your desktop
Exec=$WRAPPER
Icon=$ICON_NAME
StartupNotify=false
StartupWMClass=Ynote
Categories=Utility;
EOF
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
# Also install system-wide so GNOME's app grid picks it up without a shell restart
sudo cp "$DESKTOP_FILE" /usr/share/applications/ynote.desktop
sudo update-desktop-database /usr/share/applications/ 2>/dev/null || true
echo "Desktop entry installed (user + system-wide)"

# 6. Autostart on login
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/ynote.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Ynote
Comment=Sticky notes
Exec=$WRAPPER
Icon=$ICON_NAME
StartupNotify=false
StartupWMClass=Ynote
X-GNOME-Autostart-enabled=true
EOF
echo "Autostart configured: $AUTOSTART_DIR/ynote.desktop"

echo ""
echo "Done!"
echo "  Run now:      ynote"
echo "  Pin to dock:  right-click the dock icon while running → 'Add to Favourites'"
