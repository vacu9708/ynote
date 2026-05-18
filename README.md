# Ynote

Engineer-friendly sticky notes for Linux desktops.

![Ynote screenshot](assets/screenshots/ynote-main.png)

Ynote is a lightweight GTK desktop notes app for Ubuntu and GNOME-based Linux
systems. It is built for the kind of notes engineers keep beside their editor:
commands, debugging context, TODOs, pasted screenshots, snippets, and short
reminders that should stay visible while you work.

## Highlights

- Floating desktop notes with automatic local saving
- Always-on-top pinning for notes you need beside your editor
- Code blocks for commands and snippets
- Image insertion and image paste support
- Search inside a note
- Bold text, bullet lists, and per-note font size
- Hide notes and restore them later from the tray/menu
- Simple GTK app with no account, sync service, or cloud dependency

## Install

### Debian Package

Build the package:

```bash
./build-deb.sh
```

Install the generated package:

```bash
sudo apt install ./dist/ynote_1.1.0_all.deb
```

Run Ynote:

```bash
ynote
```

### Manual Install

For local testing, you can also install from the checkout:

```bash
./install.sh
```

The packaged `.deb` is recommended for normal use because it installs the
launcher, desktop entry, and icon in standard system locations.

## Requirements

Ynote uses Python, GTK 3, and PyGObject.

On Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0
```

## Data Location

Notes are stored locally in:

```text
~/.config/ynote/
```

The app keeps note text in `notes.json` and stores inserted images under the
same config directory.

## Development

Run directly from the repository:

```bash
python3 ynote.py
```

Build a fresh Debian package:

```bash
./build-deb.sh
```

The package metadata lives in `packaging/debian/`, and the desktop launcher is
defined in `packaging/ynote.desktop`.

## License

Ynote is released under the MIT License. See [LICENSE](LICENSE).
