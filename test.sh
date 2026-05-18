#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONDONTWRITEBYTECODE=1

echo "==> Checking Python syntax"
python3 -m py_compile ynote.py ynote/*.py tests/*.py

echo "==> Running unit tests"
python3 -m pytest

if command -v dpkg-deb >/dev/null 2>&1; then
    echo "==> Building Debian package"
    ./build-deb.sh
else
    echo "==> Skipping Debian package build: dpkg-deb not found"
fi

echo "==> All checks passed"
