#!/usr/bin/env bash
# Inside the test container: install the package as a user would, start a
# desktop (X server, window manager, session bus with accessibility), and run
# the tests against it. Arguments go to pytest.
set -euo pipefail
VERSION="$(sed -n "s/^__version__ = '\(.*\)'$/\1/p" /src/ynote/__init__.py)"
dpkg -i "/src/dist/ynote_${VERSION}.deb" >/dev/null
export XDG_RUNTIME_DIR="$(mktemp -d)"
export PYTHONDONTWRITEBYTECODE=1
exec dbus-run-session -- bash -c '
    Xvfb :99 -screen 0 1600x1000x24 -nolisten tcp >/dev/null 2>&1 &
    export DISPLAY=:99
    for _ in $(seq 50); do
        python3 -c "from Xlib import display; display.Display()" 2>/dev/null && break
        sleep 0.1
    done
    openbox --config-file /src/tests/e2e/openbox-rc.xml >/dev/null 2>&1 &
    sleep 0.5
    cd /src
    # All the tests, unless test files are named.
    paths=(tests/e2e)
    for arg in "$@"; do
        case "$arg" in tests/*) paths=() ;; esac
    done
    exec python3 -m pytest -p no:cacheprovider -q "${paths[@]}" "$@"
' bash "$@"
