# Contributing to Ynote

This page covers running Ynote from source, testing, and packaging. For how the
code is organized, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

Ynote uses Python, GTK 3, and PyGObject. On Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-xlib
```

- `python3-gi-cairo` lets PyGObject draw with cairo, which divider lines need.
- `python3-xlib` registers the global `Ctrl+Super+arrow` snap shortcut. Without
  it, the shortcut only works while a note has focus.

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
2. The unit tests (`python3 -m pytest`). Use `python3 -m pytest` rather than
   `pytest` when running them alone, so the `ynote` package can be imported.
3. A headless smoke test (`tests/smoke_launch.py`). It starts the real app in
   a virtual X server with a throwaway home directory, lets it draw a note
   that uses each kind of formatting, and fails if any Python error is
   printed. It is skipped when `xvfb-run` is not installed.
4. The Debian package build.

The smoke test only checks that the app runs without errors. To test what a
feature does, add a pytest test under `tests/` instead.

## Package

Build a Debian package into `dist/`:

```bash
./build-deb.sh
```

The package metadata lives in `packaging/debian/`, and the desktop launcher is
defined in `packaging/ynote.desktop`. Keep the dependency list in
`packaging/debian/control` and the Requirements section above in sync.

## README Screenshot

`assets/ynote-screenshot.png` is rendered from the real app, so regenerate it
after any visible UI change:

```bash
dbus-run-session -- xvfb-run -a -s "-screen 0 1600x1200x24" \
    python3 tools/readme_screenshot.py
```

The sample notes are defined in `tools/readme_screenshot.py`.

## Future Improvements

- Extract more text-buffer behavior from the GTK layer for deeper automated testing
- Add focused tests for code block, bullet list, and undo/redo state transitions
- Continue improving packaging and desktop integration across GNOME environments
