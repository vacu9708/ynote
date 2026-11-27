# Contributing to Ynote

This page covers running Ynote from source, testing, and packaging. For how the
code is organized, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

Ynote uses Python, GTK 3, and PyGObject. On Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-ayatanaappindicator3-0.1
```

- `python3-gi-cairo` lets PyGObject draw with cairo, which divider lines need.
- `gir1.2-webkit2-4.1` shows the notes of Ynote 2.0, which is being built
  (see [Ynote 2.0](#ynote-20)).
- `gir1.2-ayatanaappindicator3-0.1` draws the tray icon. Without it Ynote runs
  with no tray icon.

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

## Ynote 2.0

Ynote 2.0 draws each note, its bars and its editor, as a web page in a web
view (see [ARCHITECTURE.md](ARCHITECTURE.md#ynote-20)). While it is built, it
runs only with `YNOTE_WEB` set, beside a running 1.x. Its notes are in
`~/.config/ynote/notes-2.json`, which starts as the notes of 1.x, converted;
`notes.json` is left to 1.x, which cannot read them. The two share `images/`:

```bash
YNOTE_WEB=1 python3 ynote.py
```

The page's code is in `web/src/`, bundled into `ynote/web/note.js`, which is
committed, so building the package needs no Node.js. After changing
`web/src/`, rebuild the bundle:

```bash
(cd web && npm ci --no-bin-links)   # once
web/build.sh
```

`--no-bin-links` lets npm install on file systems without symbolic links.
`YNOTE_DEBUG=1` turns on WebKit's developer extras, the web inspector.

## Test

Run every check before committing:

```bash
./test.sh
```

It runs, in order:

1. A Python syntax check.
2. The unit tests. To run only these, use `python3 -m pytest`; plain
   `pytest` cannot import the `ynote` package. They run on the X11 backend
   like the app, so they need an X display, such as a desktop session or
   `xvfb-run -a python3 -m pytest`.
3. A headless smoke test, `tests/smoke_launch.py`, which launches the real app
   and fails on any Python error. It is skipped without `xvfb-run`.
4. The Debian package build.

Then run the end-to-end tests, which prove what Ynote does in the real app:

```bash
tests/e2e/run.sh all
```

They build the package, install it in Ubuntu 26.04 and 22.04 containers with
a virtual desktop, and drive it with real mouse and key input, reading what it
shows through its accessibility tree, the clipboard, and its files. They need
Docker and the test images, built once:

```bash
docker build --build-arg BASE=ubuntu:26.04 -t ynote-e2e:26.04 tests/e2e
docker build --build-arg BASE=ubuntu:22.04 -t ynote-e2e:22.04 tests/e2e
```

To test what a feature does, add an end-to-end test under `tests/e2e/`, one
per behavior, named after its entry in
[tests/e2e/BEHAVIORS.md](tests/e2e/BEHAVIORS.md). Unit tests under `tests/`
are for logic that needs no window, such as the Markdown conversion. A failed
end-to-end test leaves a screenshot and the app's log in `tests/e2e/out/`.

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

`assets/ynote-screenshot.png` and `assets/ynote-hidden.png` are rendered from
the real app, so regenerate them after any visible UI change:

```bash
dbus-run-session -- xvfb-run -a -s "-screen 0 2600x2000x24" \
    python3 tools/readme_screenshot.py
```

The sample notes are defined in `tools/readme_screenshot.py`. They show as
much of what Ynote does as they can: a new element of a note goes into them.
