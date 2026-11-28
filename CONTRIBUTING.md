# Contributing to Ynote

This page covers running Ynote from source, testing, and packaging. For how the
code is organized, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

Ynote uses Python, GTK 3, PyGObject, and WebKitGTK. On Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-ayatanaappindicator3-0.1
```

- `gir1.2-webkit2-4.1` shows each note, a web page in a web view.
- `gir1.2-ayatanaappindicator3-0.1` draws the tray icon. Without it Ynote runs
  with no tray icon.

To run the tests, also install:

```bash
sudo apt install python3-pytest xvfb
```

and to render the README screenshots, `python3-gi-cairo`.

## Run From Source

```bash
python3 ynote.py
```

Notes are read from and saved to `~/.config/ynote/`, the same place an
installed Ynote uses. Quit any running Ynote first: only one instance runs at
a time, so a second launch just brings the running one forward.

## The pages

Each note, its bars and its editor, is a web page in a web view (see
[ARCHITECTURE.md](ARCHITECTURE.md)). The pages' code is in `web/src/`,
bundled into `ynote/web/note.js` and `menu.js`, which are committed, so
building the package needs no Node.js. After changing `web/src/`, rebuild
the bundles:

```bash
(cd web && npm ci --no-bin-links)   # once
web/build.sh
```

`--no-bin-links` lets npm install on file systems without symbolic links.
`YNOTE_DEBUG=1` turns on WebKit's developer extras, the web inspector, and
logs what Alt+scroll does. The emoji the picker offers are made from the
`unicode-emoji-json` package by `node web/make-emoji.mjs`.

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

Then run the end-to-end tests, which prove what Ynote does in the real app:

```bash
tests/e2e/run.sh all
```

They build the package, install it in Ubuntu 26.04 and 22.04 containers with
a virtual desktop, and drive it with real mouse and key input, reading what it
shows through its accessibility tree, the clipboard, and its files. The
desktop runs openbox; what only GNOME does, as how it focuses and stacks
notes, is tested on GNOME's own window manager, run headless in the same
containers (`tests/e2e/gnome.py`). They need Docker and the test images,
built once (again after the Dockerfile changes):

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
also what the keyboard shortcuts (F1) and `ynote --version` show.

## README Pictures

`assets/ynote-screenshot.png` and `assets/feature-*.png` are rendered from
the real app, so regenerate them after any visible UI change:

```bash
dbus-run-session -- xvfb-run -a -s "-screen 0 5200x4000x24" \
    python3 tools/readme_screenshot.py
```

The sample notes, and what each picture opens, are defined in
`tools/readme_screenshot.py`. They show as much of what Ynote does as they
can: a new feature goes into them. The README and the project page,
`docs/index.html`, show the same pictures.
