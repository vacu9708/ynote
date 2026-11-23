# Contributing to Ynote

This page covers running Ynote from source, testing, and packaging. For how the
code is organized, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

Ynote uses Python, GTK 3, and PyGObject. On Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0
```

- `python3-gi-cairo` lets PyGObject draw with cairo, which divider lines need.

To run the tests, also install:

```bash
sudo apt install python3-pytest xvfb
```

## Run From Source

```bash
python3 ynote.py
```

Notes are read from and saved to `~/.config/ynote/`, the same place an
installed Ynote uses. Quit any running Ynote first: only one instance runs at
a time, so a second launch just brings the running one forward.

## Test

Run every check before committing:

```bash
./test.sh
```

It runs, in order:

1. A Python syntax check.
2. The unit tests. To run only these, use `python3 -m pytest`; plain
   `pytest` cannot import the `ynote` package.
3. A headless smoke test, `tests/smoke_launch.py`, which launches the real app
   and fails on any Python error. It is skipped without `xvfb-run`.
4. The Debian package build.

To test what a feature does, add a pytest test under `tests/`.

## Package

Build a Debian package into `dist/`:

```bash
./build-deb.sh
```

The package metadata lives in `packaging/debian/`, and the desktop launcher is
defined in `packaging/ynote.desktop`. Keep the dependency list in
`packaging/debian/control` and the Requirements section above in sync.

The package version comes from `__version__` in `ynote/__init__.py`, which is
also what About and `ynote --version` show.

## README Screenshots

`assets/ynote-screenshot.png`, `assets/ynote-hidden.png`, and `assets/ynote-customize.png` are rendered from
the real app, so regenerate them after any visible UI change:

```bash
dbus-run-session -- xvfb-run -a -s "-screen 0 3000x1400x24" \
    python3 tools/readme_screenshot.py
```

The sample notes are defined in `tools/readme_screenshot.py`.
