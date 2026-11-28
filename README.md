# Ynote

Engineer-friendly sticky notes for Linux desktops.

![Three Ynote notes: a pinned yellow note debugging a 502 error with a heading, a code block, a log screenshot, bullets with an emoji, and inline code; a green note with a table of services, an open expand holding a checklist, a folded expand, and a quote; and a blue to-do list with a link, each with its toolbar](assets/ynote-screenshot.png)

- **Everything a note needs:** code blocks you copy one command at a time,
  tables, expands that fold away, checklists, lists, quotes, headings, inline
  code, links, emoji, and pasted images, edited as in Confluence
- **Markdown in and out:** copy to other apps as Markdown, paste Markdown in
  with its formats, or type it, such as `**bold**` or `- `; `/` inserts
  the rest
- **Seven colors, opacity, pinned on top, or collapsed** to the title bar
- **Hidden notes** stay out of the way, and find searches every note,
  hidden ones too
- **Snap** notes into half-screen columns with `Alt` and the arrows

![Left: a pink note with its menu open, showing new note, hidden notes, colors, opacity, font size, and the keyboard shortcuts. Middle: a note finding restart in all notes, listing matches in hidden notes. Right: the hidden notes, each a card of its note's colors](assets/ynote-hidden.png)

## Install

Download `ynote_<version>.deb` from the
[latest release](https://github.com/vacu9708/ynote/releases/latest), then:

```bash
sudo apt install ./ynote_*.deb   # keep the ./
```

Run `ynote` or open it from the app grid; it starts at login from then on.
Press **F1** in a note for the keyboard shortcuts. Notes are saved in
`~/.config/ynote/`; notes from Ynote 1.x open as they were, and their old
file is kept as `notes-old.json`.

Ynote needs GTK 3, WebKitGTK, and Python 3.10 or later, as on Ubuntu 22.04
and later, Wayland included.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[ARCHITECTURE.md](ARCHITECTURE.md).

## License

MIT, see [LICENSE](LICENSE). The fonts in [ynote/fonts](ynote/fonts) are
under the SIL Open Font License that comes with them.
