# Ynote

Engineer-friendly sticky notes for Linux desktops.

![Two Ynote notes: a pinned note debugging a 502 error with a command, a log screenshot, and the cause, and a to-do list with a link](assets/ynote-screenshot.png)

Ynote keeps the notes engineers want beside their editor (commands, code
snippets, debugging context, screenshots, and to-dos) in small floating
windows on the desktop. Hidden notes stay one search away, so Ynote also works
as a set of runbooks and cheat sheets.

Ynote runs on Debian- and Ubuntu-based Linux desktops with GTK 3 and Python
3.10 or later, including Wayland sessions. It is developed on Ubuntu 26.04.

## Features

- Floating notes that save automatically, with always-on-top pinning
- Hide notes you don't need on screen, and find any of them again with
  **All notes** search
- Code blocks you can copy one command at a time
- Checklists, bullet lists, bold text, dividers, links, and backtick
  formatting for paths and names
- Images pasted or inserted into notes
- Seven note colors, adjustable opacity, and collapsing a note to its title bar
- Snap notes into half-screen columns with the keyboard

![Left: a short note's search bar with All notes checked, where searching restart lists the match in that note and matching lines from the hidden notes k8s, nginx, and Deploy. Right: the Hidden Notes window listing six hidden notes with Restore and Restore All buttons](assets/ynote-hidden.png)

## Install

Download `ynote_<version>.deb` from the
[latest release](https://github.com/vacu9708/ynote/releases/latest), then
install it from the download folder. `apt` also installs what Ynote needs.

```bash
sudo apt install ./ynote_*.deb   # keep the ./
```

Open **Ynote** from the app grid, or run `ynote`. From then on it also starts
when you log in. To turn that off, right-click a note's title bar and uncheck
**Start at Login**.

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

Your notes stay in `~/.config/ynote/`.

</details>

## Using Ynote

### The note window

| Where | Action |
| --- | --- |
| Title bar | Drag to move the note. Double-click to maximize it, and again to restore it. |
| `▾` | Collapse the note to its title bar. It becomes `▸`; click it to expand the note again. A maximized or tiled note cannot be collapsed, and a collapsed note cannot be resized. |
| `📌` | Keep the note above other windows. Click again to turn it off. |
| `+` | Create a new note next to this one. |
| `✕` | Hide the note. See [Hidden notes](#hidden-notes). |
| `▤` | Open the list of hidden notes. |
| Edges and corners | Drag to resize the note. |
| Right-click the title bar or bottom bar | Rename the note, set its color, opacity, and font size, minimize, turn **Start at Login** on or off, open About to see the version, delete the note after you confirm (an empty note goes right away), or quit Ynote. |
| Right-click the text | Undo, redo, search, insert an image, or insert a divider. |

Opacity makes only the note's background see-through, so text and the bars stay
opaque. It needs a compositing desktop; without one the slider is disabled.

Long lines wrap to fit the note and rewrap when you resize it. A word too long
for one line is split, with a `-` shown at the break; the `-` is not added to
your text. Lines in code blocks stay on one line and scroll sideways instead.

### Formatting

| Format | How |
| --- | --- |
| Bold | `Ctrl+B` or the `B` button |
| Backtick format | Type text between backticks, like `` `this` ``, or select text and press `Ctrl+E` or the `` ` `` button. The backticks are removed and the text turns red, italic, and underlined. |
| Bullet list | Type `- ` at the start of a line, or press `Ctrl+8` or the `•` button. `Tab` and `Shift+Tab` change the indent. `Backspace` on an empty bullet removes it. |
| Checklist | Type `[ ] ` at the start of a line, or press `Ctrl+9` or the `☐` button. Click a box or press `Ctrl+Enter` to check it. Checked items turn gray. |
| Link | `http` and `https` URLs become links. `Ctrl+click` one to open it. |
| Code block | `Ctrl+Shift+C` or the `</>` button. In a code block, double-click a line to select that one command, or triple-click to select the whole block. |
| Divider | Type `---` on its own line, or right-click and choose **Insert Divider**. `Backspace` or `Delete` removes it. |
| Image | Paste an image with `Ctrl+V`, or right-click and choose **Insert Image**. Right-click an image to remove it. |

Typed `- ` or `[ ] ` turned into a list item you didn't want? Press `Ctrl+Z` right away to
keep the plain text.

### Other shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+F` | Search the note. Check **All notes** to list matches in every note, hidden ones too, and click one to open it. `Esc` closes the search bar. |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+Super+←` / `→` | Snap the note into the left or right half of its monitor. Press again at the edge to move it to the next monitor. |
| `Ctrl+Super+↑` / `↓` | Move the note up or down by its own height |
| `Ctrl+Super+` two arrows | Send the note to that corner |

### Hidden notes

Hiding a note with `✕` takes it off the screen without deleting it. To bring it
back, click `▤` on any note or choose **Hidden Notes** from the tray icon menu,
then select the note and click **Restore**, or double-click it. **Restore All**
brings back every hidden note. The most recently hidden note is listed first,
and `↑` / `↓` reorder the list.

## Where your notes are stored

Everything is saved locally in `~/.config/ynote/`: note text in `notes.json`
and inserted images in `images/`. To back up your notes, copy that folder.

## Contributing

To run Ynote from source, run the tests, or build the package, see
[CONTRIBUTING.md](CONTRIBUTING.md). For how the code is organized, see
[ARCHITECTURE.md](ARCHITECTURE.md).

## License

Ynote is released under the MIT License. See [LICENSE](LICENSE).
