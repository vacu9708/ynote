#!/usr/bin/env bash
# Bundles web/src into ynote/web: note.js, a note's page, and menu.js, the
# page of the popup window that shows menus. They are committed, so building
# and installing Ynote need no Node.js. Run after changing web/src:
#   (cd web && npm ci --no-bin-links) once, then web/build.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
node node_modules/esbuild/bin/esbuild src/note.js src/menu.js --bundle --format=iife \
    --target=es2022 --minify --legal-comments=eof \
    --outdir=../ynote/web "$@"
