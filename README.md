# Ynote

Engineer-friendly sticky notes for Linux desktops.

![Two Ynote notes: a pinned note debugging a 502 error with a command, a log screenshot, and the cause with a fire emoji, and a to-do list with a link and a rocket emoji](assets/ynote-screenshot.png)

Ynote keeps the notes engineers want beside their editor (commands, code
snippets, debugging context, screenshots, and to-dos) in small floating
windows on the desktop.

Ynote runs on Debian- and Ubuntu-based Linux desktops with GTK 3 and Python
3.10 or later, including Wayland sessions. It is developed on Ubuntu 26.04.

## Features

- **Floating notes** that save automatically, with always-on-top pinning
- **Seven colors, adjustable opacity, and collapsing** a note to its title bar
- **Hidden notes** you don't need on screen, which **All notes** search still
  finds
- **Code blocks** you can copy one command at a time
- **Checklists, bullet lists, bold text, dividers, links, backtick formatting**
  for paths and names, **emoji**, and **images**
- **Snapping** notes into half-screen columns with the keyboard

![A green note at 35% opacity over a terminal full of log lines, with its right-click popover open to show the color swatches, the opacity slider, and the font size buttons, and a collapsed note below it](assets/ynote-customize.png)

![Left: a short note's search bar with All notes checked, where searching restart lists the match in that note and matching lines from the hidden notes k8s, nginx, and Deploy. Right: the Hidden Notes window listing six hidden notes with Restore and Restore All buttons](assets/ynote-hidden.png)

## Install

Download `ynote_<version>.deb` from the
[latest release](https://github.com/vacu9708/ynote/releases/latest), then
install it from the download folder. `apt` also installs what Ynote needs.

```bash
sudo apt install ./ynote_*.deb   # keep the ./
```

Open **Ynote** from the app grid, or run `ynote`. From then on it also starts
when you log in. To turn that off, uncheck **Start at Login** in a note's
right-click menu.

<details>
<summary>Upgrading from an <code>install.sh</code> install</summary>

Remove what `install.sh` left behind, or the old copy keeps starting instead
of the package. Then log out and back in.

```bash
sudo rm /usr/local/bin/ynote
rm ~/.local/share/applications/ynote.desktop ~/.config/autostart/ynote.desktop
```

</details>

<details>
<summary>Uninstall</summary>

```bash
sudo apt remove ynote
```

</details>

## Good to know

Buttons show their shortcut when you hover over them. These are the things the
buttons don't show:

- **Right-click** the title bar or bottom bar for the note's color, opacity,
  font size, rename, and delete. Double-click the title bar to maximize.
- Typing `- ` or `[ ] ` at the start of a line makes a bullet or a checklist,
  `---` alone on a line makes a divider, and `` `text` `` turns red italic.
- Paste an image with `Ctrl+V`.
- In a code block, double-click a line to select one command, or triple-click to
  select the whole block. `Ctrl+click` opens a link.
- `Ctrl+F` searches the note; check **All notes** to search every note.
- `Ctrl+Super+` arrows snap a note into the left or right half of its monitor,
  move it up or down, or send it to a corner.
- `✕` hides a note. Bring it back from `▤` or the tray icon's **Hidden Notes**.

## Where your notes are stored

Everything is saved locally in `~/.config/ynote/`: note text in `notes.json`
and inserted images in `images/`. To back up your notes, copy that folder.
Uninstalling Ynote keeps it.

## Contributing

To run Ynote from source, run the tests, or build the package, see
[CONTRIBUTING.md](CONTRIBUTING.md). For how the code is organized, see
[ARCHITECTURE.md](ARCHITECTURE.md).

## License

Ynote is released under the MIT License. See [LICENSE](LICENSE).
