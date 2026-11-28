# Ynote behaviors

The list the end-to-end tests are written from, kept up to date as tests are
added or changed. One item is one test, named after its id. Each is checked
in the real app: real mouse and key input (XTEST), and results read from
notes.json, the clipboard, the accessibility tree (AT-SPI), or pixels.

Marks: **[WM]** needs a window manager (the test desktop runs openbox) ·
**[px]** checked by pixels · **[2204]** also checked on Ubuntu 22.04

When what should happen is unclear, Ynote follows Confluence. Where it does
not, the item says why.

Not tested, until they matter: the tray menu (simple, with little room for
edge cases), opacity (B6: it needs a compositor, and matters little), and
placing notes across two monitors (D4, D9: much effort for little).

---

## A. Starting, saving, files

- A1 Starting with no notes at all makes a new note at the mouse pointer
- A2 With one hidden note and none shown, that note opens at the pointer
- A3 With several hidden notes and none shown, the Hidden Notes window opens at the pointer
- A4 An edit is saved without quitting (notes.json changes)
- A5 Each start copies notes.json to notes.json.bak
- A6 An empty notes.json does not replace a good .bak
- A7 An unreadable notes.json is renamed notes.json.broken-<time>, a dialog says so, and image cleanup is skipped
- A8 A note that fails to open is saved back unchanged, with a warning, and image cleanup is skipped
- A9 Notes open stacked as they were when Ynote quit [WM]. Openbox stacks them right even without the restacking GNOME (mutter) needs, so that part is not shown here
- A10 notes.json keeps Korean as it is and each range on one line, read and written as UTF-8
- A11 Starting Ynote while it runs brings its notes forward instead of a second copy [WM]
- A12 `ynote --version` prints the version
- A13 Quit with a dialog open (Help, About, Delete) quits; a Delete confirmation counts as cancelled
- A14 A note saved off screen, as after a monitor was unplugged, moves onto the primary monitor
- A15 On an X server with no primary monitor, the first note is still placed on screen
- A16 [2204] On 22.04 (PyGObject 3.42) the app starts and shows its notes
- A17 A note moved and resized is saved where it is, and opens there again [WM]

## B. A note's window

- B1 The + button makes a square note right of the current one, else left, wholly on a monitor
- B2 ✕ hides the note and puts it first in Hidden Notes
- B3 The window manager's close button or Alt+F4 hides that note; Ynote keeps running [WM]
- B4 Delete asks first for a note with text; an empty note goes at once
- B5 One of seven colors is picked in the popover and saved
- B6 Opacity is saved, and text in a see-through note keeps an opaque strip behind it (not tested)
- B7 A− and A+ step the font size by one, between 8 and 32
- B8 A new title is saved; a note without one shows a dimmed, italic Untitled
- B9 Collapsing leaves the title bar, opening restores the height, and the state is saved
- B10 A double click on the title bar maximizes and restores; the size before is saved [WM]
- B11 While maximized, collapse is disabled; while collapsed, maximize does nothing [WM]
- B12 Every edge resizes the note [WM]
- B13 Pin keeps the note on top, and is saved [WM]
- B14 Right-clicking the title or bottom bar opens the popover: color, opacity, font size, title, delete, Start at Login, Help, About
- B15 Start at Login turned off turns the autostart entry off, and it stays off on later starts
- B16 About shows the version, where notes are saved, and where the running copy is
- B17 Help lists only shortcuts nothing on screen shows (not the menus' Markdown or shortcuts)

## C. Hidden Notes

- C1 The Hidden Notes window lists hidden notes, the latest hidden first
- C2 Notes hidden together (Hide All) come first in that order
- C3 A double click or Restore shows the note and closes the window
- C4 Restore right after the window opens restores the note hidden last (first, chosen already)
- C5 The arrow buttons reorder hidden notes, and the order is saved
- C6 Restore All
- C7 The eye button's tooltip tells how many notes are hidden

## D. Arranging notes

- D1 Alt+Left/Right snap into the left or right half of the monitor, keeping height and y
- D2 Alt+Up/Down alone move the note up or down by its height, keeping x and width, and stop at the screen's edge
- D3 Alt with two arrows sends the note to a corner
- D4 Alt+Left/Right again from an edge column goes to the next monitor, if there is one (not tested)
- D5 A collapsed note snaps to its new width at once
- D6 Snapping does nothing while maximized [WM]
- D7 Alt+scroll steps through notes from the latest used; the order holds while Alt is held, so scrolling back retraces it, and the note stopped on counts as the latest once Alt is let go [WM]
- D8 Small scrolls add up to one step, and a quick second one is ignored
- D9 Notes are placed within the work area, panels left out, across monitors (not tested)

## E. Text formats: bold, heading, inline code

- E1 Ctrl+B bolds or unbolds a selection; without one it turns bold on or off for what is typed
- E2 With bold text before the cursor, Bold is on and the Format button lights up
- E3 At the start of a line, the text after the cursor counts
- E4 At the start of a list item's, to-do's, or quote's text, after its marker, the text after the cursor counts
- E5 At the left edge of bold within a line, Bold is off: the text before the cursor counts, as in Confluence
- E6 A selection shows a format on only when all of it has it
- E7 Bold turned off in the middle of bold text types plain text there, splitting it
- E8 Enter turns every format off
- E9 Ctrl+H makes the cursor's line, or every line a selection touches, a heading; again takes it away when all are headings
- E10 Heading on an empty line makes the text typed next a heading; again cancels it
- E11 Code lines, dividers, and list items do not become headings
- E12 Enter at the end of a heading starts a plain line
- E13 A heading is bold with Bold off; Bold on makes it bolder, in the font's Black weight [px]
- E14 Making a line a heading, or taking the heading away, keeps the bold in it
- E15 Bold in a heading goes out and comes back as Markdown, `# Title **bold**`
- E16 Ctrl+E turns inline code on or off, or makes a selection code or plain
- E17 Inline code has a padding character at each end, which copying leaves out
- E18 Text typed right after inline code is plain; typed inside it, code
- E19 Turning code on or off at its edge steps the cursor over the padding
- E20 Backspace and Delete next to the padding take the character beyond it
- E21 Deleting the last character of inline code takes its padding too
- E22 A selection never ends on the padding: keys step over it, a drag stops at the text
- E23 Code turned off in its middle splits it, each part with its padding
- E24 Enter does not carry inline code to the next line

## F. Markdown typed into a note

- F1 `**text**` typed makes bold; stars around spaces, or in a glob like `*.txt`, stay as they are
- F2 `` `text` `` typed makes inline code, with the cursor after it
- F3 Backticks in a code block, in inline code, or on two lines do not make code
- F4 `# ` on an empty line makes the next text a heading; before text, its line; after text, `#` stays
- F5 ` ``` ` on an empty line starts a code block; after text it stays text
- F6 `- ` makes a bullet, `[ ] ` a to-do, also after a bullet; not in a code block
- F7 `> ` starts a quote
- F8 A line of `---` is a divider
- F9 Each item of the Insert and Format menus shows its icon, shortcut, and Markdown

## G. Lists: bullets and to-dos

- G1 Ctrl+8 toggles a bullet and Ctrl+9 a to-do; Ctrl+8 on a to-do makes it a bullet
- G2 Enter starts the next item of the kind (a to-do unchecked); Enter on an empty item ends the list
- G3 Enter at an item's start or in its marker adds an empty item above; in its text, splits it
- G4 Tab and Shift+Tab indent and outdent by one level, one tab character
- G5 Tab and Shift+Tab over a selection indent each item in it and keep the selection; a selection ending at a line's start leaves that line out; one without list items is left to GTK
- G6 Backspace at a top item's start takes the marker; at a nested item's, empty or not, outdents it one level
- G7 Delete at a line's end, joining the next item, takes its marker first
- G8 A click on a box checks it without moving the cursor; checked items are gray
- G9 Ctrl+Enter checks or unchecks the to-dos on the selected lines only
- G10 The cursor and selection ends never go into a marker; a click on a marker stays on its line
- G11 Home stays at an item's start; Shift+Home once selects its text, twice its marker too
- G12 Shift+Left from an item's start takes the marker, then the line break; back gives them up in that order; a mouse selection takes a marker it reaches over
- G13 Left from an item's start goes to the end of the line before
- G14 Bold over several list lines leaves the markers and line breaks without it
- G15 Bullets and to-dos do not apply to code block lines, as Ctrl+8 in a code block
- G16 A list item does not become a heading
- G17 An older note's lists indented by spaces get tabs when it opens, keeping their formats; a list typed after spaces gets tabs too
- G18 Formats on markers and line breaks in an older note are taken off when it opens

## H. Quotes

- H1 Insert > Quote or `> ` starts a quote, with a bar beside it
- H2 Enter continues a quote; Enter on an empty line ends it
- H3 A wrapped quote's later rows start as far in as its text [px]

## I. Code blocks

- I1 Insert > Code block, or ` ``` ` on an empty line
- I2 The box is as wide as the longest line, and follows edits; lines do not wrap, the block scrolls sideways [px]
- I3 A double click in a code block selects the line without its line break; a triple click, the whole block
- I4 Empty lines in a code block stay in it, through pastes and replaced selections too
- I5 Text pasted or typed over a selection in a code block stays code, as over a line selected by a double click
- I6 A paste into code takes the text as it is, without reading Markdown
- I7 Lines with formats made a code block show their Markdown (`# Title`, `**bold**`, `- item`) in one block; Ctrl+Z brings them back in one step
- I8 Lines already code stay as they are; a line with an image is left out
- I9 A code block made plain again keeps the Markdown as text
- I10 A search match in a code block is highlighted [px]
- I11 A long code block (3000 lines) opens fast and typing in it stays fast
- I12 A selection over several lines of a code block looks like GTK's, out to the right edge

## J. Dividers, links, emoji

- J1 A `---` line is drawn as a line, and the cursor skips it either way
- J2 http and https addresses are underlined links: Ctrl+click opens one, a click only places the cursor, and a tooltip says so
- J3 A link leaves out the punctuation after it, and keeps parentheses, queries, and ports
- J4 Insert Emoji comes first in the text's right-click menu
- J5 Emoji are drawn larger without making their line taller [px]

## K. Images

- K1 Ctrl+V pastes an image; Insert > Image inserts a file
- K2 Image files are saved in images/, and one no note uses is cleaned up
- K3 Images still in the undo history or Ynote's clipboard are not cleaned up
- K4 An image in a table cell counts as in use

## L. Tables

- L1 Insert > Table adds a table with a header row and the cursor in its first cell
- L2 A click in a cell puts the cursor where it was clicked, also right of or below the text
- L3 A drag selects in a cell, and a double click selects a word
- L4 Tab and Shift+Tab go to the next or previous cell; Tab past the last cell adds a row and goes to its first cell, which shows and takes typing
- L5 Tab on a list item in a cell indents it
- L6 Enter makes a new line in a cell, not a row, and the table grows
- L7 Up and Down at a cell's first or last row go to the cell above or below, or out of the table; Esc leaves it
- L8 The arrows go into a table from the lines around it: the first cell from above, the last from below
- L9 Esc or Down from a table last in an expand goes past it, not back into the table
- L10 A cell's right-click menu: Add Row Below, Add Column Right, Delete Row, Delete Column, Delete Table; cells added show and take typing; deleting the last row or column deletes the table
- L10a Deleting the header row makes the next row the header, in bold. Unlike Confluence the table keeps a header, which a Markdown table must have
- L11 A deleted table comes back with Ctrl+Z, and takes clicks
- L12 Ctrl+Z in a cell undoes that cell's edits
- L13 A cell holds lists, quotes, code blocks, inline formats, and images
- L14 The Format and Insert menus and the shortcuts act on the cell with the cursor; Insert > Table is off in a cell
- L15 A column is as wide as its text, measured in its fonts (bold, inline code); in a note too narrow, narrow columns keep their width and wide ones share the rest
- L16 Short inline code, as `x | y`, does not wrap in a narrow column
- L17 The header row is shaded and bold, and its bold turns off; an empty header cell, and a line after Enter in one, start bold
- L18 A note has one selection: a double click in a cell, then a click elsewhere, leaves no selection behind
- L19 Typing or Backspace over a selection across a table removes it without a crash, and Ctrl+Z brings it back
- L20 Backspace at the start of the line below a table goes into its last cell, or takes that line away when empty; Delete at the end of the line above does nothing
- L21 A click right of a table puts the cursor beside it, not in a cell; typing there goes on the line after it, as in Confluence
- L21b Beside a table, Enter opens a line after it (or goes to the empty one there), Backspace goes into the last cell, Delete does nothing, and the arrows go into the table
- L22 Text in cells is found by search, in the note and across all notes; Enter on a match selects it in its cell
- L23 A folded expand hides a table in it
- L24 A table copies as a GitHub Markdown table: `<br>` for a line break in a cell, `\|` for a pipe, code lines as inline code, no bold markers in the header
- L25 A pasted Markdown table becomes a table, `<br>` a line break in a cell, its header bold
- L26 Markdown pasted into a cell keeps its formats; a table is not put in a cell
- L27 A table in the 1.13 format, rows of tab-separated text, becomes a table of cells when its note opens
- L28 A cell's right-click opens one menu, not the note's too
- L29 Cells are saved with their text, formats, and images in the note's tables field, and open as they were

## M. Expands

- M1 Insert > Expand puts the selected lines in it; inserted on the empty last line, it leaves a line after it
- M2 A click on the arrow, or Ctrl+Enter on the title, folds or opens it; folding moves a cursor inside to the title
- M3 An expand holds code blocks, lists, tables, and other expands
- M4 Enter on its empty last line goes on below the expand
- M5 Backspace after an expand takes an empty line into it; Delete never joins a line to its end
- M6 Backspace at the title's start keeps what it holds
- M7 An expand never ended gets an end, and an end without one is taken out
- M8 A search match in a folded expand shows it open until the search closes
- M9 An expand copies as `<details>` and pastes back as an expand
- M10 The cursor does not rest on an expand's end line

## N. Clipboard

- N1 Copied text goes to other apps as Markdown: headings, bold, inline code, fenced code, list levels, to-dos, quotes, dividers, tables, expands
- N2 Code alone is copied as it is, without fences
- N3 A paste into another note keeps formats, images, and tables exactly
- N4 Once another app takes the clipboard, its text is pasted, not Ynote's formats
- N5 Markdown from another app pastes in with its formats, and links as their text and address
- N6 A list, heading, or code block pasted after text starts a line of its own
- N7 Ctrl+Shift+V pastes the text alone, without reading Markdown
- N8 Cut and paste brings everything back, tables included
- N9 Copying out and pasting back as Markdown gives the same note, but for a blank line before a divider
- N10 Names with underscores and lone stars stay text; inline code holding a backtick gets longer backticks
- N11 Middle-click pastes and drags carry no invisible characters, such as an empty code line's mark

## O. Undo and redo

- O1 Ctrl+Z and Ctrl+Shift+Z keep the scroll position and put the cursor where the edit was
- O2 A table's shape changes and cell edits are steps of the note's undo
- O3 After undo, the Format button follows the formats at the cursor

## P. Search

- P1 Ctrl+F opens the search bar with All notes on, this note's matches first
- P2 With All notes off, only this note is searched
- P3 Matching ignores case and takes the query literally, not as a pattern
- P4 Each match shows the note's title and the matching line, cut around the match; a hidden note's mark always shows
- P5 Up and Down in the entry pick a match, the cursor staying in the entry; Enter opens it, or the first
- P6 Opening a match brings its note forward, restoring it if hidden, and selects the match
- P7 Highlights go when the search closes
- P8 Esc closes the search

## Q. Drawing and wrapping [px]

- Q1 A long line wraps at the note's width; a code block's lines do not
- Q2 In a note with Korean, every line is as far from the next
- Q3 Inline code that wraps has padding at the end of the row it wraps from
- Q4 Inline code that starts a line and wraps lines up its later rows, box and text, with the first, with padding
- Q5 Inline code that starts within a line and wraps starts its later rows' boxes with the text
- Q6 Rows of wrapped inline code with Korean in it do not overlap
- Q7 A word of code too long for its row starts on it, leaving no empty box before
- Q8 Code boxes have the same padding on all sides; an inline code box sits in the middle of its line
- Q9 List markers (dots, boxes) are drawn at an em-based size and do not make their line taller
- Q10 After Enter in a list, quote, code block, or table, and any key the note handles, the new line is in view
- Q11 Bold in a heading is drawn bolder, in English and Korean, on 22.04 too [2204]
- Q12 A see-through note keeps an opaque strip behind text, table cells too

## R. Notes from older versions

- R1 Inline code padded by plain spaces or en spaces (U+2002) gets figure spaces
- R2 Lists indented by spaces get tabs
- R3 Formats on markers and line breaks are taken off
- R4 Tables of tab-separated rows (1.13) become tables of cells
- R5 A note saved without newer fields (color, opacity, collapsed...) gets their defaults
- R6 What is saved stays readable by an older version, but for the tables field

## S. Korean through an input method, in Ynote 2.0

Typed through ibus with its Korean engine, as on a Korean desktop, into a note
of 2.0 (`YNOTE_WEB`).

- S1 Korean is saved as composed: space and Enter end a syllable, and Backspace in one takes its last jamo
- S2 Enter while composing in a list item ends the syllable and starts the next item
- S3 Markdown typed around Korean, as `**굵게**` or `` `코드` ``, makes it bold or code
- S4 Ctrl+B while composing keeps the syllable as it was and bolds what follows
- S5 Korean typed into a table cell, empty or selected by Tab, stays on the cell's line
- S6 Korean typed into an expand's title and content stays where it is typed

## T. The window of a 2.0 note: bars, menus, find

A note of 2.0 (`YNOTE_WEB`). Its menus show in a popup window of their own,
so they may reach past the note.

- T1 A toolbar button applies its format to the selection
- T2 A menu reaches past a small note, and choosing an item applies it: a divider puts the cursor on a line below it
- T3 A click outside a menu closes it and does nothing else
- T4 Keys move in a menu and Enter chooses
- T5 Esc closes a menu and nothing changes
- T6 A color from the note menu is the note's, and saved
- T7 Font size from the note menu is saved
- T8 Right-click in a table cell offers rows and columns: Insert row below adds one
- T9 Copy on a code block copies the whole block
- T10 Delete from the note menu asks on the note, and Delete deletes it
- T11 F2 renames the note
- T12 Find (Ctrl+F) moves through the matches with Enter, and Esc leaves the current one selected
- T13 A match in a folded expand opens it
- T14 A narrow note puts the end of the toolbar into ＋
- T15 A tool's tooltip shows its name, the Markdown typed for it, and its keys, and only that
- T16 A note is not resized smaller than it can be used: 180 × 120, or its title bar collapsed
- T17 A note saved smaller than that opens at the least size
- T18 Hidden notes, in the note menu (or the tray), lists them latest hidden first, and choosing one shows it (1.x's arrows to reorder them are gone: the latest hidden first is the order, and Find's All notes finds any)
- T19 Show all shows every hidden note
- T21 Collapse leaves the note as tall as its title bar, and Expand brings back its height (GNOME made a collapsed note 1px tall, from what its web view asks for; openbox, which the tests run, sized it right either way, so this test does not catch that bug)
- T22 A click outside closes the shortcuts, as any menu, and does nothing else; a note whose menu is open closes it when another window takes the focus
- T23 The note menu starts with New note and Hidden notes, which have no button, and ends with Delete, away from a quick click
- T24 A wheel notch scrolls as far as in 1.x, about the view's height to the 2/3 power, and at once: WebKit's animated scroll, drawn in software, lagged on the desktop (Xvfb does not animate it, so the test does not catch that)
- T25 Find's All notes stays where it is as it is turned on and off, beside Close
- T20 F1 shows the keyboard shortcuts, made from the actions, with Ynote's version and where its notes are

## U. Editing in a 2.0 note

Where 2.0 follows Confluence over 1.x, the item says so.

- U1 A double click in a code block selects the line clicked, usually one command
- U2 A triple click in a code block selects the whole block
- U3 Bold in a heading is drawn bolder than the heading
- U4 Bold turns off in a table's header, which is bold by its own format
- U5 Typing in a new table's header starts bold, and Table inserts a 3 × 3 table
- U6 Deleting a table's header row makes the next row its header
- U7 /expand inserts an expand
- U8 / opens a menu that what is typed after it narrows, and Enter inserts the first, such as the date
- U9 A path typed after a space, as /var/log/syslog, stays as typed
- U10 Esc closes the / menu and leaves what was typed
- U11 Enter on an empty line of an expand makes another line in it, as in Confluence (1.x left the expand)
- U12 Enter on an empty line of code makes another line of code, as in Confluence (1.x left the block)
- U13 A note always ends with a line, so Down goes below a code block, an expand, or a table at its end
- U14 Right at the end of a table's last cell, in an expand, then typing, makes a line below the table, in the expand, as in Confluence
- U15 Ctrl+V pastes an image from the clipboard
- U16 Find's All notes (Alt+A) lists the matches in every note, hidden ones too, and Enter shows the note chosen
- U17 The note menu holds nothing a title bar button does
- U18 Down from a table's last row in an expand goes below the expand, as in Confluence
- U21 Find's Match case, regular expression, and All notes stay as last set, for every note and the next start, and apply in All notes too
- U22 A drag up over a table selects everything it passes
- U23 A drag from below the text selects up from the end, as the editor fills the note
- U24 A drag from the empty line below a table, up over it, selects everything it passes (WebKit moved the drag's start to the table's edge)
- U19 // where a word starts types today's date, as in Confluence
- U20 // after other text, as in https://, stays as typed

## V. Copy and paste in a 2.0 note

As in 1.x (N). Ctrl+C, X, and V in the text are the window's, which puts
Markdown on the clipboard; the right-click menu does the same.

- V1 Copied text goes to other apps as the Markdown 1.x gives the same note: headings, bold, inline code, code, lists and their levels, to-dos, quotes, dividers, expands, tables
- V2 Code alone is copied as it is, without fences
- V3 A paste into another note keeps everything as it was
- V4 Once another app takes the clipboard, its text is pasted, not Ynote's copy
- V5 Markdown from another app pastes in with its formats: headings, bold, code, to-dos, tables
- V6 A list pasted after text starts a line of its own
- V7 Ctrl+Shift+V pastes the text alone, a line for each line, without reading Markdown
- V8 Cut and paste brings everything back, tables and expands included
- V9 Markdown pasted into code goes in as it is
- V10 Copy as Markdown (Ctrl+Shift+M, or the note menu) copies the whole note as Markdown, wherever the cursor is

## X. A 2.0 note among other windows

- X1 A note on top stays above another app's window [WM]
- X2 Alt+scroll steps through the notes from the latest used [WM]
- X3 Scrolling back while Alt is held retraces the steps [WM]
- X4 A quick second scroll is one step
- X5 A hidden note shows again where it was
- X6 Alt+scroll brings up stacked notes one after another, as in 1.x [WM] (right after a start, with another app focused, GNOME left the note behind when presented at the scroll's time; it is now presented at the X server's time, which openbox, which the tests run, does not need)
