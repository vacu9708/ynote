#!/usr/bin/env bash
set -euo pipefail
umask 022

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"
CONTROL_FILE="$ROOT_DIR/packaging/debian/control"

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "error: dpkg-deb is required to build the package" >&2
    exit 1
fi

VERSION="$(awk '/^Version: / { print $2; exit }' "$CONTROL_FILE")"
PACKAGE="$(awk '/^Package: / { print $2; exit }' "$CONTROL_FILE")"
DEB_FILE="$DIST_DIR/${PACKAGE}_${VERSION}_all.deb"
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ynote-deb.XXXXXX")"
trap 'rm -rf "$BUILD_DIR"' EXIT
chmod 0755 "$BUILD_DIR"

mkdir -p \
    "$BUILD_DIR/DEBIAN" \
    "$BUILD_DIR/usr/bin" \
    "$BUILD_DIR/usr/share/applications" \
    "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps" \
    "$BUILD_DIR/usr/share/ynote"
mkdir -p "$DIST_DIR"

install -m 0644 "$CONTROL_FILE" "$BUILD_DIR/DEBIAN/control"
install -m 0755 "$ROOT_DIR/packaging/debian/postinst" "$BUILD_DIR/DEBIAN/postinst"
install -m 0755 "$ROOT_DIR/packaging/debian/postrm" "$BUILD_DIR/DEBIAN/postrm"

install -m 0755 "$ROOT_DIR/ynote.py" "$BUILD_DIR/usr/share/ynote/ynote.py"
install -m 0644 "$ROOT_DIR/icon.png" "$BUILD_DIR/usr/share/ynote/icon.png"
install -m 0644 "$ROOT_DIR/icon.png" "$BUILD_DIR/usr/share/icons/hicolor/256x256/apps/ynote.png"
install -m 0644 "$ROOT_DIR/packaging/ynote.desktop" "$BUILD_DIR/usr/share/applications/ynote.desktop"

cat > "$BUILD_DIR/usr/bin/ynote" <<'EOF'
#!/usr/bin/env bash
GDK_BACKEND=x11 exec python3 /usr/share/ynote/ynote.py "$@"
EOF
chmod 0755 "$BUILD_DIR/usr/bin/ynote"

dpkg-deb --build --root-owner-group "$BUILD_DIR" "$DEB_FILE"
echo "$DEB_FILE"
