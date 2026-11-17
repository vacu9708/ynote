#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONDONTWRITEBYTECODE=1

echo "==> Checking Python syntax"
python3 -m py_compile ynote.py ynote/*.py tests/*.py

echo "==> Running unit tests"
if ! python3 -c 'import pytest' 2>/dev/null; then
    echo "error: pytest is not installed. Run: sudo apt install python3-pytest" >&2
    exit 1
fi
python3 -m pytest

if command -v xvfb-run >/dev/null 2>&1 && command -v dbus-run-session >/dev/null 2>&1; then
    echo "==> Launching the app headless (smoke test)"
    xvfb-run -a python3 tests/smoke_launch.py
else
    echo "==> Skipping smoke test: xvfb-run or dbus-run-session not found"
fi

if command -v dpkg-deb >/dev/null 2>&1; then
    echo "==> Building Debian package"
    ./build-deb.sh
else
    echo "==> Skipping Debian package build: dpkg-deb not found"
fi

echo "==> All checks passed"
