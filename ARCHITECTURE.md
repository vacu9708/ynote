# Ynote Architecture

Ynote is a single-process GTK 3 app written in Python with PyGObject. One
`Gtk.Application` (`PostItApp`) owns every note window, and each note is a
`NoteWindow` holding a `Gtk.TextView`. Everything a user creates is saved
under `~/.config/ynote/`.

## Modules

This diagram shows which module owns or uses which. The pure modules have no
GTK dependency, so they are unit-tested without a display.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#FFFFFF', 'primaryTextColor': '#1A202C', 'primaryBorderColor': '#4A5568', 'lineColor': '#64748B', 'edgeLabelBackground': '#FFFFFF', 'titleColor': '#1A202C'}}}%%
flowchart LR
    Main["ynote.py, main.py<br/>entry point"]

    subgraph GTK["GTK layer"]
        App["app.py<br/>PostItApp"]
        Window["note_window.py<br/>NoteWindow"]
        Editor["editor.py<br/>Editor"]
        Table["table.py<br/>table of editors"]
        Manager["note_manager_window.py<br/>Hidden Notes window"]
        Tray["tray.py<br/>tray indicator"]
    end

    subgraph Pure["Pure logic, unit-tested"]
        Storage["storage.py"]
        Images["images.py"]
        Autostart["autostart.py"]
        Models["models.py"]
        Snap["snap.py"]
        Search["search.py"]
        Links["links.py"]
        Markdown["markdown.py"]
        Sections["sections.py"]
    end

    Main -->|starts| App
    App -->|owns one per note| Window
    App -->|owns| Manager
    App -->|uses| Tray
    App -->|uses| Storage
    App -->|uses| Images
    App -->|uses| Autostart
    Window -->|is an| Editor
    Window -->|uses| Models
    Window -->|uses| Snap
    Window -->|uses| Search
    Editor -->|uses| Links
    Editor -->|uses| Markdown
    Editor -->|uses| Sections
    Editor -->|holds| Table
    Table -->|cells are| Editor

    classDef node fill:#FFFFFF,stroke:#4A5568,color:#1A202C
    class Main,App,Window,Editor,Table,Manager,Tray,Storage,Images,Autostart,Models,Snap,Search,Links,Markdown,Sections node
    style GTK fill:#FFF4D6,stroke:#B7791F,color:#3D2C00
    style Pure fill:#E8F8EF,stroke:#2F855A,color:#143C2B
```

| Module | Responsibility |
| --- | --- |
| `ynote.py`, `ynote/main.py` | Entry point. Handles `--version`, selects GTK's X11 backend, then runs `PostItApp`. |
| `ynote/__init__.py` | Holds `__version__`, the only place the version is set. |
| `ynote/app.py` | Application lifecycle, tray icon, the set of notes, hidden-note order, the shared rich clipboard, and saving. |
| `ynote/note_window.py` | One note's window: its title bar, bottom bar with the Format and Insert menus, search bar, snapping, collapsing, saving, and the right-click popover with color, opacity, and font size. A `NoteWindow` is an `Editor`. |
| `ynote/editor.py` | The text editor: formats, lists, quotes, code, tables, expands, images, typed Markdown, undo/redo, the clipboard, and drawing what GTK does not. It needs only `self.tv` and what its owner sets (`app`, the font size and colors); `_queue_save()` and `_refresh_format_buttons()` are hooks the owner overrides. |
| `ynote/table.py` | A table whose cells are editors: `TableWidget` and `CellEditor`. |
| `ynote/sections.py` | Finds the expands in a note's lines. |
| `ynote/note_manager_window.py` | The Hidden Notes window: list, reorder, and restore hidden notes. |
| `ynote/tray.py` | Loads the application indicator library and makes the tray indicator, which the desktop draws and positions. Also words the tray menu's labels. |
| `ynote/models.py` | Fills defaults into saved note data, so older `notes.json` files still load. |
| `ynote/storage.py` | Reads JSON files and writes them atomically. |
| `ynote/images.py` | Image metadata, and finding and deleting image files no note uses. |
| `ynote/snap.py` | Computes a snapped note rectangle from monitor work areas. |
| `ynote/search.py` | Finds a query in every note for the search bar's All notes mode. |
| `ynote/links.py` | Finds `http` and `https` URLs in note text. |
| `ynote/markdown.py` | Converts a note's text and formats to Markdown for the clipboard, and pasted Markdown back. |
| `ynote/autostart.py` | The per-user login autostart entry. |
| `ynote/config.py` | Paths and constants. |
| `ynote/app_fonts.py` | Registers the fonts in `ynote/fonts/` for Ynote alone: the Black weight of Noto Serif and Noto Serif KR, for bold in a heading, which most systems lack. They come with their SIL Open Font License. |
| `ynote/styles.py` | The note color palette and the GTK CSS built from it. It has no GTK import, so it is unit-tested. |

## Note data model

`notes.json` is a list with one object per note, in UTF-8 with text such as
Korean as it is and each range on one line, so a person can read it
(`to_json()`). Formatting is stored as character ranges over plain text, not
as markup:

```json
{
  "id": "0b6e…", "title": "tmux", "text": "Sessions\ntmux new -s work",
  "x": 120, "y": 80, "w": 300, "h": 320,
  "on_top": false, "hidden": false, "sort_order": 0.0, "font_size": 14,
  "color": "yellow", "opacity": 1.0, "collapsed": false,
  "bold_ranges": [], "heading_ranges": [[0, 8]], "code_ranges": [[9, 25]],
  "backtick_ranges": [],
  "images": []
}
```

| Field | Meaning |
| --- | --- |
| `text` | The note text, including the special characters below. |
| `bold_ranges`, `heading_ranges`, `code_ranges`, `backtick_ranges` | `[start, end)` character offsets into `text`. GTK buffer offsets count characters, so they match Python string indices. |
| `images` | `{file, original_name, offset}` per image. `offset` is where its placeholder character sits in `text`. |
| `tables` | `{offset, rows}` per table, at its placeholder character like an image. `rows` are lists of cells, each a rich state: `text` and `bold`, `heading`, `code`, `backtick`, and `images`, as the clipboard holds them. An older Ynote shows nothing there and drops the field when it saves. |
| `x`, `y`, `w`, `h` | Window position and size. A maximized note saves the rectangle it had before, and a collapsed note saves its expanded height as `h`. |
| `hidden`, `sort_order` | Whether the note is hidden, and its place in the Hidden Notes list. |
| `on_top`, `font_size` | Always-on-top and the note's font size. |
| `color` | A name from the palette in `styles.py`. An unknown name loads as the default, `yellow`. |
| `opacity` | Background opacity from `0.0` to `1.0`, clamped on load. Only the note body is see-through. The title bar, bottom bar, and text stay opaque. |
| `collapsed` | Whether the note is shown as its title bar only. |

Some structure lives in the text itself:

| In `text` | Meaning |
| --- | --- |
| `U+FFFC` (`IMAGE_ANCHOR`) | Where an image is shown. |
| `U+2060` (`CODE_ANCHOR`) | An invisible character that lets an empty line carry the code tag. It is stripped when text goes to the system clipboard, and tagged `invisible` by `_hide_code_anchors()` so that GTK leaves it out of the selection that middle click pastes and of a drag. Text read from the buffer therefore includes hidden characters. |
| `• `, `☐ `, `☑ `, or `▍ ` at the start of a line | A bullet, an open to-do, a done to-do, or a quote. Each nesting level adds a leading tab. |
| A line that is exactly `---` | A divider. The dashes are hidden and `_draw_dividers()` paints a line over them. |
| `▾ ` or `▸ ` at the start of a line, and a line holding only `U+2064` (`EXPAND_END`) | The title of an open or folded expand, and the end of the innermost expand open. Everything between them is what it holds. |
| `U+2063` (`TABLE_MARKER`) at the start of a line | A row of a table as tables were before their cells were editors, cells separated by tabs. Such rows, from an older note or pasted Markdown, become a table when the note opens or the paste lands. |

Emoji sizing, dividers, grayed-out done to-dos, links, and search
highlights are tags derived from the text while the app runs, and are never
saved. A version without one of these features still shows the text as is.

Other files under `~/.config/ynote/`:

- `images/` holds a copy of every inserted image, named by a UUID, so a note
  keeps working after the original file moves.
- `settings.json` records app-wide state. Today that is only whether login
  autostart was already set up once.

## Editing, undo, and saving

This diagram shows what an edit causes, from the keystroke to the files on
disk.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'actorBkg': '#FFFFFF', 'actorBorder': '#4A5568', 'actorTextColor': '#1A202C', 'actorLineColor': '#64748B', 'signalColor': '#1A202C', 'signalTextColor': '#1A202C', 'noteBkgColor': '#FFF4D6', 'noteBorderColor': '#B7791F', 'noteTextColor': '#1A202C', 'labelBoxBkgColor': '#E2E8F0', 'labelBoxBorderColor': '#4A5568', 'labelTextColor': '#1A202C', 'loopTextColor': '#1A202C'}}}%%
sequenceDiagram
    box rgb(255, 255, 255)
    actor User
    participant Buf as Gtk.TextBuffer
    participant Win as NoteWindow
    participant App as PostItApp
    participant Disk as ~/.config/ynote
    end
    Note over User,Disk: Edits stay in memory until typing pauses for 600 ms, then every note is saved
    User->>Buf: keystroke or formatting action
    Buf->>Win: changed signal
    Win->>Win: restart the 600 ms snapshot and save timers
    Note over Win: Snapshot timer fires
    Win->>Win: append text, ranges, and images to undo history
    Note over Win,Disk: Save timer fires
    Win->>App: request to save all notes, save_all()
    loop every NoteWindow
        App->>Win: request for the note dict, to_dict()
        Win-->>App: note dict
    end
    App->>Disk: notes.json, written to a temp file and renamed
    App->>Disk: deletion of image files nothing references
```

- Moving or resizing a note also starts the save timer.
- Undo history keeps the last 100 states per note and lives only in memory.
- While the app runs, an image is kept if a note, any note's undo history, or
  the rich clipboard still refers to it. That way undo can bring back a
  deleted image. Quitting saves once more and keeps only images the saved
  notes use.

## Startup

1. `main()` sets `GDK_BACKEND=x11` before GTK loads. Otherwise GTK would pick
   any Wayland socket it finds. See [Why X11](#why-x11). It also sets
   `IBUS_ENABLE_SYNC_MODE=1`, unless set, so that an input method such as
   Korean's answers each key in turn: answered asynchronously, a busy computer
   took keys out of order, and Enter after a Korean word could land after the
   next word had started.
2. `PostItApp.do_startup()` creates the config directories, sets up login
   autostart on an installed app's first run, loads the CSS, and creates the
   tray icon.
3. `_load()` copies `notes.json` to `notes.json.bak`, creates a `NoteWindow`
   for each saved note, or one empty note when there are none, then deletes
   image files no saved note uses. If `notes.json` exists but cannot be
   read, it is renamed to `notes.json.broken-<time>` instead of being
   overwritten, the user is warned, and image cleanup is skipped for that run
   so the kept notes' images survive. A note whose window fails to open is
   kept as it was read and saved back unchanged, with image cleanup skipped
   and a warning, so a bug in opening notes never deletes them.
4. `do_activate()`, which also runs when Ynote is started while it runs,
   brings the visible notes forward. When none is visible, it opens the one
   hidden note, or the Hidden Notes window when more are hidden, or makes a
   new note when none is. Each opens centered on the mouse pointer, inside
   the work area of its monitor (`snap.center_at()`), as does the empty note
   of a first start.

## Other mechanisms

- **Copy and paste.** Copying in a note stores the text, ranges, and images
  in `PostItApp` for a paste into a note, and puts the same text on the system
  clipboard as Markdown (`markdown.to_markdown()`), or as it is when it is all
  code, so a command pastes into a terminal without fences. Pasting uses the
  stored state only while Ynote still owns the clipboard. Text from another
  app is read as Markdown (`markdown.from_markdown()`) and pasted with its
  formats, except into code, which takes text as it is. A note is not stored
  as Markdown: search, undo, and the editor work on the text as shown, and
  Markdown is only how text crosses the clipboard. `Ctrl+Shift+V` pastes the
  text alone, and a backtick in it, or in any code, never starts inline code.
- **Tables.** A table (`table.py`) is a `TableWidget`, a grid of
  `CellEditor`s, at a child anchor alone on its line, as an image is. Each
  cell is an `Editor` of its own, so it holds lines, lists, code, and images
  as a note does; it takes the note's font size and colors, and its changes
  are saved with the note and are a step of the note's undo
  (`_on_table_changed()`). The Format and Insert menus and the shortcuts act
  on `_active_editor()`, the note's text or the cell last focused. Tab moves
  between cells, and Up and Down at a cell's edge, or Esc, go on to the next
  cell or out of the table; the cursor coming onto a table's line by a key
  goes into it. A click in a cell ends there, since a text view passes it on
  to the note's, which would place its own cursor at the table. Text deleted
  over a table's anchor takes the table with it. A column is as wide as its widest line, shrunk to fit the
  note. The table draws its lines and shaded header itself, and a folded
  expand hides it. Searching covers the cells: `buffer_text()` puts their text
  after the note's, and `show_match()` finds the cell. On the clipboard a
  table is a GitHub Markdown table, with `<br>` for a line break in a cell.
- **Expands.** An expand is a section of a note that folds away, a box with
  a title as in Confluence. `sections.py` finds them in the text, as lists of
  lines, and `_apply_sections()` hides a folded one's content and end line
  with a derived `invisible` tag that also takes the line break, so a hidden
  line takes no room. An open one's end line stays, set very small, as the
  room at the bottom of its box, and the cursor skips it as it does a divider.
  Its title and content get margins for how many expands deep they are, and
  code boxes, tables, and dividers start at `_line_left()`, inside the box.
  `_draw_sections()` draws the boxes and the chevrons over the title marks,
  each a button that lights up under the pointer, which are text: folding replaces one with the other, so an expand is saved,
  undone, and copied as text. `_normalize_sections()` removes an end that
  ends nothing, ends an expand left open at the end of the note, and keeps a
  line after the last end for the cursor. While a search highlights a match
  in a folded expand, it is shown open without changing the note, and folds
  again when the search closes. Choosing a match in the All notes list opens
  it. On the clipboard an expand is HTML's `<details>`.
- **Login autostart.** `autostart.enable_on_first_run()` writes
  `~/.config/autostart/ynote.desktop` once per user, and only when the
  `ynote` command is installed. The Start at Login menu item adds or removes
  that file.

- **Color and opacity.** Each note has one `Gtk.CssProvider` built by
  `styles.note_css()`, attached to the window and both bars. The alpha needs
  an RGBA visual set before the window is realized. Below 100%,
  `_draw_text_backing()` paints an opaque strip behind each row of text so it
  stays readable.
- **Line spacing.** Every line has the same spacing, set on the text view,
  whatever its format. Its total is `LINE_SPACING`, or a pixel more where the
  fonts need it, and how it divides above and below is worked out from them so
  that an inline code box sits in the middle of its line. Code boxes may
  reach into it.
- **List markers.** A bullet or a to-do box is not text to the user, though it
  is characters in the note (`• `, `☐ `, `☑ `), so notes saved before and the
  clipboard keep working. Everything that treats text as text steps around it:
  `_marker_end()` says where a marker ends, the cursor and the ends of a
  selection are moved out of one once GTK has moved them, a format is applied
  with `_tag_text()` to the text after the marker and never to a line break,
  since a format on a break reaches into the next line and moves its indent,
  a list item is never made a heading or a line of code, and Backspace at the
  start of an item outdents it one level, or removes the whole marker from one
  at the top level. Each level is a tab, as wide as `INDENT_SPACES` spaces of
  the note's font; an item indented by spaces, as items were before, gets tabs
  when its note opens. Moving left from the start of an item goes on to the end
  of the line before, while selecting left takes the whole marker first and
  the line break with the next step; a mouse selection takes a marker it
  reaches over. A bullet in a line of code is code, with no marker. The
  characters are drawn transparent by a derived tag, scaled to fit in the line
  and spaced to take the room the drawing needs, and `_draw_list_markers()`
  draws a filled circle or a box, sized by `BULLET_SIZE` and `CHECKBOX_SIZE` in
  em, over them. Because the drawing does not come from a font, a larger one
  does not make its line taller.
- **Even lines.** A line is as tall as the tallest font that draws it, and
  the note's font lacks most scripts other than Latin, so a line of Hangul,
  Japanese, Arabic, or Thai is drawn in whichever font this computer falls back
  to, and its height differs from a line of Latin. In a note with such text,
  `_even_lines()` lays out each line whole in the note's font, as it is in the
  note, so Pango picks the same fonts, and reads its ascent and descent the
  way GTK rounds them. `even_slots()` then gives every line the spacing that
  puts its baseline the same distance from the top and bottom of the room it
  takes: the most any line needs, and no less than a Latin line has. A font
  with room of its own takes the place of the spacing, so lines are no
  further apart than they have to be. Nothing in it names a font or a script.
  The rows of a wrapped line are as far apart as lines are, but a row can
  lack the tall font, and inline code's boxes reach into the spacing, so a
  line with inline code keeps at least the note's spacing between its rows.
  Emoji, and the dingbats drawn like them, keep their own height; headings,
  code, and dividers are spaced on their own. Notes without non-Latin text are
  unchanged.
- **Code boxes.** Code blocks and inline code share one box, as in CSS: the
  font's line area plus padding, `CODE_PAD` on the sides and `CODE_PAD_Y`
  above and below, so the padding is the same on all sides and does not depend
  on which letters are inside. They have a light gray background for a block
  and a darker one for inline code. A code block also keeps
  `CODE_BLOCK_MARGIN` from the lines around it. `_refresh_code_spacing()`
  scales code text so its lowercase letters are as tall as the body's, and
  works out the spacing from the fonts.
- **Code blocks.** `_draw_code_blocks()` draws one outlined box per run of code
  lines, as wide as the longest line. A multi-line selection inside a code
  block is drawn there too, because GTK would paint it across the whole note.
  The room inside the box is line spacing on the code tag. Nothing in code is
  formatted, so `_toggle_code_block()` turns the lines it makes code into the
  Markdown they would be copied as, with every format taken off.
- **Inline code.** A text tag cannot have an outline or padding, so the tag
  only sets the font and color, and `_draw_inline_code()` draws the outlined
  box around the characters of each display line of every `backtick_ranges`
  range. The box is placed from the code character's own rectangle, whose
  top is the top of the code font, raised with it, not the top of the row.
  The ranges keep the name of the backticks that typed them, which are
  removed once the text is styled.
- **Padding of inline code.** A text view makes room for nothing but
  characters, and letter spacing, which Pango splits between both sides of a
  character, cannot make room beside a letter without opening a gap on its far
  side. So the padding is a figure space (`CODE_PAD_CHAR`) at each end of the
  range, tagged as code and set in the body font by `_pad_tag`. It is about
  half an em wide, which is the padding and the gap from the text beside the
  code: the box is drawn `CODE_GAP` inside it at each end. No line breaks
  beside it, so a word of code too long for its row does not leave the
  padding alone on the row before. It is not a space
  shrunk to a width: GTK draws the cursor as tall as the font of the
  character after it, so a smaller space gave a smaller cursor beside the
  code, and the space of the body font is too narrow.
  `_normalize_code_pads()` gives every range its two spaces and removes one
  that is only spaces, whenever the text changes and when a note is loaded,
  restored, or pasted into, so an old note gets them the first time it is
  opened, with a plain space or the en space of a note from before 1.14 at an
  end of a range made one, and a range that
  comes from typing, a selection, or backticks has them too. They are in the
  saved text, and Ctrl+C leaves them out. A figure space may only be at the end
  of a range as its padding: `_pad_kind()` says which one it is.
  Where code wraps, its box reaches past the last character before the wrap
  by as much as at its end. A line that starts with code moves the rows it
  wraps to in by the padding space (`_code_hang_tag`, a negative indent), and
  their boxes start the padding before the text, in line with the first
  row's. Code that starts within a line wraps to rows whose boxes start with
  the text: GTK cannot move a row in alone.
- **The cursor and the padding.** The cursor is inside the code on one side
  of a padding space and outside on the other, and `_sync_format_state()`
  takes that from `_pad_kind()`. Turning code on or off at an edge steps the
  cursor over the space, so it is where the text will go, as in Slack. In the
  middle of code, turning it off changes no text, and what is typed there makes
  two ranges, which `_normalize_code_pads()` gives their spaces. Backspace and
  Delete next to a padding space take the character beyond it, since the box
  has no character of its own there. A selection never ends on a padding
  space (`_keep_pads_out_of_selection()`): an end moved by a key goes on past
  it, and one dragged by the mouse stops short of it.
- **Room around code.** Like dividers, `_apply_code_margins()` derives tags
  from the text after every change: spacing above the first and below the last
  line of a code block, and `_pad_tag` on the padding spaces. It runs once the
  edit is done, because a line typed into a code block gets its tag after the
  buffer reports the change.
- **Formats at the cursor.** Bold, inline code, and heading are each on or off
  at the cursor, shown by the Format button, lit while any is on, and checked
  in its menu. `_sync_format_state()`
  takes them from the text the cursor is attached to whenever it moves, also
  when deleting text or undoing moves it, a menu item or shortcut toggles one, typed text gets the ones that are on
  and none of the others, also inside a bold or code range, which splits it,
  and Enter turns them all off. `heading_ranges` cover whole lines, so on an empty
  line Heading applies to the text typed there next. A heading is bold, and
  Bold is off in it until turned on, which makes it bolder, as in Confluence:
  `_refresh_heading_bold()` puts the heading's Black weight where bold and a
  heading meet, whenever either changes. Making a line a heading or taking it
  away leaves its bold as it is. The text at the start of a
  list item or quote, after its marker, takes formats from the text after
  the cursor, as at the start of a line.
- **Format and Insert menus.** The bottom bar keeps one button for the formats
  of text and one for the elements to insert, so it does not grow with each
  new element. `_popup_bar_menu()` opens a `Gtk.Menu`, a window of its own,
  so it can be larger than the note, whose rows show the item, the Markdown
  typed for it, and its shortcut. What a row shows is true: typing `# `,
  `**text**`, and ```` ``` ```` turns into a heading, bold text, and a code
  block as typed, each its own undo step, like `- ` and `` `text` ``.
- **Right-click popover.** A `Gtk.Popover` is drawn inside the window it is
  attached to, so one that does not fit the note, always the case for a
  collapsed note, is attached to a transparent window of its own.
- **Collapse.** A collapsed note hides everything below the title bar and
  cannot be resized, which keeps the window manager from tiling or maximizing
  an empty note. A maximized or tiled note cannot be collapsed, because the
  window manager ignores its resizes.

## Ynote 2.0

Ynote 2.0 is being built beside 1.x, and runs only with `YNOTE_WEB` set
(`config.WEB`), with its notes in `~/.config/ynote-web/`. The editor of 1.x,
a `Gtk.TextView` with structure drawn over it, gives way to ProseMirror, the
editor Confluence's is built on, in a WebKit web view. The whole note is the
web page: its title bar, bottom bar, menus, and editor, so they share one
design. The GTK window stays, frameless, for what only a window can do.

| Part | Responsibility |
| --- | --- |
| `ynote/web_note_window.py` | `WebNoteWindow`, one note's window: position, size, moving and resizing on the page's request, collapse, keep on top, hide, snapping, saving. It answers what `PostItApp` asks of a note, as `NoteWindow` does. |
| `ynote/web/note.html`, `note.css` | The note page and its look. The window sets the note's colors and font size on `:root`. |
| `web/src/` | The page's code, bundled by `web/build.sh` into `ynote/web/note.js`: `schema.js` (what a note holds), `editor.js` (keys, typed Markdown), `commands.js` (what menus and shortcuts do), `views.js` (expand and to-do buttons), `links.js`, `chrome.js` (the bars and menus), `main.js` (`window.ynote`). |
| `ynote/convert.py` | Turns a 1.x note, text with ranges, into a 2.0 document, and a document into plain text for search. |

- **Content.** A note is saved as its ProseMirror document's JSON, in its
  `doc` field, in place of `text` and the ranges. A note without `doc` is a
  1.x note and is converted when it opens (`convert.note_doc()`). A bullet
  and a to-do are items of one list (`list_item.attrs.checked` is `null` for a
  bullet), an expand is a node holding a title and blocks, and a table's cells
  hold any block but a table. Links are found in the text as it changes, and
  not saved.
- **Page and window.** The page sends JSON messages through
  `window.webkit.messageHandlers.ynote`; `_on_message()` runs `_do_<type>()`.
  `ready` makes the window send the note with `ynote.load()`, `changed`
  carries the document after every edit, and `move` and `resize` start a move
  or resize from the mouse press the window saw last, as a window manager
  needs. The window changes the page with `ynote.set()`.
- **One web process.** Every note's web view is related to another's, so all
  pages run in one web process: one each would take about 250 MB per note.
  Hardware acceleration is off, which saves hundreds of MB on some systems.
- **Corners.** With a compositing window manager, the window has an RGBA
  visual and the page a transparent background, so the note's corners are
  round. Without one, they are square.

## Why X11

Ynote always runs on GTK's X11 backend, through XWayland on a Wayland session.
Native Wayland does not let an app place its own windows or keep them on top,
and Ynote depends on both for saved positions, snapping, and pinning. The tray
icon is an application indicator, which the desktop draws and positions. It
replaced `Gtk.StatusIcon`, an X11 mechanism whose menu GNOME Shell under Wayland
opened in the middle of the screen.

## Testing

The pure modules have unit tests in `tests/`. GTK code is covered by the
headless smoke test, which launches the real app. See
[CONTRIBUTING.md](CONTRIBUTING.md#test).
