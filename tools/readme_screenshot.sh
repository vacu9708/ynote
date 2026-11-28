#!/usr/bin/env bash
# Render the README pictures (tools/readme_screenshot.py) in the end-to-end
# test image, under a compositing manager, so a see-through note shows what
# is behind it. Writes assets/ynote-screenshot.png and assets/ynote-features.png.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker run --rm --init -v "$ROOT":/src -w /src ynote-e2e:26.04 bash -c '
    export XDG_RUNTIME_DIR="$(mktemp -d)" PYTHONDONTWRITEBYTECODE=1
    dbus-run-session -- xvfb-run -a -s "-screen 0 5200x4000x24" bash -c "
        xcompmgr -n & sleep 1
        python3 tools/readme_screenshot.py
    "
    chown "$(stat -c %u:%g /src)" assets/ynote-*.png
'
