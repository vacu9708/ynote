# Ynote

Engineer-friendly sticky notes for Linux desktops: commands, code, tables,
and checklists in small notes beside your editor, edited as in Confluence
and copied out as Markdown.

**[Download the .deb](https://github.com/vacu9708/ynote/releases/latest)** ·
Ubuntu 22.04 and later, and Debian-based desktops · X11 and Wayland · free
and open source (MIT)

![Three Ynote notes: a pinned yellow note debugging a 502 error with a heading, a code block, a log screenshot, bullets with an emoji, and inline code; a green note with a table of services, an open expand holding a checklist, a folded expand, and a quote; and a blue to-do list with a link](assets/ynote-screenshot.png)

<table>
<tr>
<td width="50%"><img src="assets/feature-slash.png" alt="The / menu open in a note, listing heading, lists, checklist, code block, table, quote, divider, expand, image, emoji, and date, each with its Markdown and keys"><br><b>Type <code>/</code> to insert anything</b>, or Markdown such as <code>**bold**</code>, <code>- </code>, and <code>```</code></td>
<td width="50%"><img src="assets/feature-table.png" alt="A table in a note with its right-click menu: insert rows and columns, delete them, or the table"><br><b>Tables</b> whose cells hold lists, code, and formats; right-click for rows and columns</td>
</tr>
<tr>
<td><img src="assets/feature-find.png" alt="Find in a note with All notes on, listing matches for restart in this note and in three hidden notes"><br><b>Find in every note</b>, hidden ones too, plain or as a regular expression</td>
<td><img src="assets/feature-hidden.png" alt="The hidden notes listed below a note's title bar, each a card of its note's color, with Show all"><br><b>Hidden notes</b> stay out of the way until you need them</td>
</tr>
<tr>
<td><img src="assets/feature-menu.png" alt="A note's menu: new note, hidden notes, rename, copy as Markdown, seven colors, opacity, solid while in use, font size, keyboard shortcuts, start at login, and delete"><br><b>Seven colors, opacity, and font size</b>; pin a note on top or collapse it to its title bar</td>
<td><img src="assets/feature-emoji.png" alt="The emoji picker below the cursor: a field to find emoji by name, the recent ones, and every group"><br><b>Emoji</b> found by name, the ones you use first</td>
</tr>
<tr>
<td colspan="2"><img src="assets/feature-shortcuts.png" alt="The keyboard shortcuts in two columns: text, insert, lists and expands, tables, copy and paste, notes, and arranging notes"><br><b>Every action has a key</b>: press <kbd>F1</kbd> in a note for the list</td>
</tr>
</table>

- **Markdown in and out:** copied text goes to other apps as Markdown, and
  code alone as it is, ready for a terminal; pasted Markdown keeps its
  formats
- **Code blocks** copy one command at a time: double-click its line, or use
  the block's Copy button
- **Arrange notes from the keyboard:** snap them into half-screen columns
  with <kbd>Alt</kbd> and the arrows, and step through them with
  <kbd>Alt</kbd> and the wheel
- **Local:** notes save as you type, in `~/.config/ynote/`, and start with
  you at login

## Install

Download `ynote_<version>.deb` from the
[latest release](https://github.com/vacu9708/ynote/releases/latest), then:

```bash
sudo apt install ./ynote_*.deb   # keep the ./
```

Run `ynote` or open it from the app grid. Notes from Ynote 1.x open as they
were, and their old file is kept as `~/.config/ynote/notes-old.json`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[ARCHITECTURE.md](ARCHITECTURE.md).

## License

MIT, see [LICENSE](LICENSE). The fonts in [ynote/fonts](ynote/fonts) are
under the SIL Open Font License that comes with them.
