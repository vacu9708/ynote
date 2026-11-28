# Ynote behaviors

The list the end-to-end tests are written from, kept up to date as tests are
added or changed. One item is one test, named after its id; an item that
names others in parentheses is proven by them. Each is checked in the real
app, on Ubuntu 26.04 and 22.04: real mouse and key input (XTEST), and
results read from notes.json, the clipboard, the accessibility tree
(AT-SPI), or pixels.

Marks: **[WM]** needs a window manager (the test desktop runs openbox) ·
**[GNOME]** runs on GNOME's window manager, mutter, headless with Xwayland
and its own input (`gnome.py`) · **[px]** checked by pixels

When what should happen is unclear, Ynote follows Confluence. Where it does
not, the item says why.

Not tested, until they matter: the tray menu (simple, with little room for
edge cases), opacity (B6: it needs a compositor), and placing notes across
two monitors (D4, D9: much effort for little).

---

## A. Starting, saving, files

- A1 Starting with no notes at all makes a new note at the mouse pointer
- A2 With one hidden note and none shown, that note shows where it was
- A3 With several hidden notes and none shown, their list opens at the pointer
- A4 An edit is saved without quitting (notes.json changes)
- A5 Each start copies notes.json to notes.json.bak
- A5b Notes saved by Ynote 1.x open converted and are saved as 2.0 saves them, the file of 1.x kept as notes-old.json
- A6 An empty notes.json does not replace a good .bak
- A7 An unreadable notes.json is renamed notes.json.broken-<time>, a dialog says so, and image cleanup is skipped
- A8 A note that fails to open is saved back unchanged, with a warning, and image cleanup is skipped
- A9 Notes open stacked as they were when Ynote quit [WM]
- A10 notes.json keeps Korean as it is and each range on one line, read and written as UTF-8
- A11 Starting Ynote while it runs brings its notes forward instead of a second copy [WM]
- A12 `ynote --version` prints the version
- A13 Quitting while Delete asks on the note quits and keeps the note
- A14 A note saved off screen, as after a monitor was unplugged, moves onto the primary monitor
- A15 On an X server with no primary monitor, the first note is still placed on screen (not tested)
- A17 A note moved and resized is saved where it is, and opens there again [WM]

## B. A note's window

- B1 New note (Ctrl+N) makes a square note right of the current one, else left, wholly on a monitor
- B2 Hide (✕) hides the note and puts it first in the hidden notes
- B3 The window manager's close button or Alt+F4 hides that note; Ynote keeps running [WM]
- B4 Delete asks on the note first (T10)
- B5 One of seven colors is picked in the note menu and saved (T6)
- B6 Opacity fades everything below the title bar, down to 0%, and is saved; with Solid while in use (always at 0%), the note shows whole while in use (not tested: it needs a compositor)
- B7 Font size steps by one, between 8 and 32 (T7)
- B8 A new title (F2) is saved; a note without one shows a dimmed Untitled
- B9 Collapsing leaves the title bar, Expand brings back the height, and the state is saved (T21)
- B10 A double click on the title bar maximizes and restores; the size before is saved [WM]
- B11 While maximized, collapse is disabled; while collapsed, maximize does nothing [WM]
- B12 Every edge resizes the note [WM]
- B13 Always on top keeps the note on top, and is saved [WM]
- B14 Right-clicking the title bar opens the note menu (T23)
- B15 Start at login turned off turns the autostart entry off, and it stays off on later starts
- B16 The keyboard shortcuts (F1) show the version and where the notes are saved (T20)
- B17 The keyboard shortcuts list every action with keys or Markdown (T20)

## C. Hidden notes

- C1 Hidden notes lists them, the latest hidden first, each on its own color (T18)
- C2 Notes hidden together (Hide all, in the tray) come first in that order (not tested: the tray)
- C3 Choosing one shows it where it was (T18, X5)
- C6 Show all shows every hidden note (T19)
- C7 The note menu's Hidden notes tells how many notes are hidden

## D. Arranging notes

- D1 Alt+Left/Right snap into the left or right half of the monitor, keeping height and y
- D2 Alt+Up/Down alone move the note up or down by its height, keeping x and width, and stop at the screen's edge
- D3 Alt with two arrows sends the note to a corner
- D4 Alt+Left/Right again from an edge column goes to the next monitor, if there is one (not tested)
- D5 A collapsed note snaps to its new width at once
- D6 Snapping does nothing while maximized [WM]
- D7 Alt+scroll steps through notes from the latest used; the order holds while Alt is held, so scrolling back retraces it, and the note stopped on counts as the latest once Alt is let go [WM] (X2, X3, X7, X10)
- D8 Small scrolls add up to one step, and a quick second one is ignored (X4)
- D9 Notes are placed within the work area, panels left out, across monitors (not tested)

## E. Text formats: bold, heading, inline code

- E1 Ctrl+B bolds or unbolds a selection; without one it turns bold on or off for what is typed
- E2 With bold text before the cursor, Bold is on and its button lights up
- E3 At the start of a line, the text after the cursor counts
- E4 At the start of a list item's, to-do's, or quote's text, after its marker, the text after the cursor counts
- E5 At the left edge of bold within a line, Bold is off: the text before the cursor counts, as in Confluence
- E6 Ctrl+B on a selection partly bold takes the bold off, as in Confluence (1.x made all of it bold)
- E7 Bold turned off in the middle of bold text types plain text there, splitting it
- E8 Enter turns every format off
- E9 Ctrl+H makes the cursor's line, or every line a selection touches, a heading; again takes it away when all are headings
- E10 Heading on an empty line makes the text typed next a heading; again cancels it
- E11 Code lines, dividers, and list items do not become headings
- E12 Enter at the end of a heading starts a plain line
- E13 A heading is bold; bold in it is bolder, in the font's Black weight [px] (U3)
- E14 Making a line a heading, or taking the heading away, keeps the bold in it
- E15 Bold in a heading goes out and comes back as Markdown, `# Title **bold**`
- E16 Ctrl+E turns inline code on or off, or makes a selection code or plain
- E18 Text typed right after inline code is plain, as in Confluence; typed inside it, code
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
- F9 Each tool's tooltip shows its name, the Markdown typed for it, and its keys (T15)

## G. Lists: bullets and to-dos

- G1 Ctrl+8 toggles a bullet and Ctrl+9 a to-do; Ctrl+8 on a to-do makes it a bullet
- G2 Enter starts the next item of the kind (a to-do unchecked); Enter on an empty item ends the list
- G3 Enter at an item's start adds an empty item above; in its text, splits it
- G4 Tab and Shift+Tab indent and outdent an item by one level
- G5 Tab over a selection indents each item in it
- G6 Backspace at a top item's start takes its bullet; at a nested item's, outdents it one level
- G7 Delete at a line's end joins the next item's line to it
- G8 A click on a to-do's box checks it without moving the cursor; done items are gray
- G9 Ctrl+Enter checks or unchecks the to-dos on the selected lines only
- G13 Left from an item's start goes to the end of the line before
- G15 Bullets and to-dos do not apply to code block lines, as Ctrl+8 in a code block
- G16 A list item does not become a heading (E11)
- G17 An older note's lists indented by spaces open nested (R2)

## H. Quotes

- H1 Quote (＋ or /quote) or `> ` starts a quote, with a bar beside it (F7, T4)
- H2 Enter continues a quote; Enter on an empty line ends it
- H3 A wrapped quote's later rows start as far in as its text [px]

## I. Code blocks

- I1 Code block (Ctrl+Shift+C), or ` ``` ` on an empty line (F5)
- I2 Lines in a code block do not wrap: the block, as wide as the note, scrolls sideways, as in Confluence
- I3 A double click in a code block selects its line; a triple click, the whole block (U1, U2)
- I4 Enter on an empty line of code makes another line of code, as in Confluence (U12)
- I5 Text typed over a selection in a code block stays code (U1)
- I6 A paste into code takes the text as it is, without reading Markdown (V9)
- I7 Lines with formats made one code block show their Markdown (`# Title`, `**bold**`, `- item`); Ctrl+Z brings them back in one step
- I8 Lines already code stay as they are; lines with an image are not made code, which would lose it
- I9 A code block made plain again keeps its lines, the Markdown in them as text
- I10 A find match in a code block is lit [px]
- I11 A long code block (3000 lines) opens fast and typing in it stays fast

## J. Dividers, links, emoji

- J1 Up and Down select a divider, and typing replaces it, as in Confluence (1.x skipped it)
- J2 http and https addresses are links: Ctrl+click opens one, and a click only places the cursor
- J3 A link leaves out the punctuation after it, and keeps parentheses, queries, and ports
- J4 Emoji… (the right-click menu, ＋, /emoji, or Ctrl+.) finds emoji by name and puts one at the cursor; the ones used last come first

## K. Images

- K1 Ctrl+V pastes an image (U15); Image… in ＋ inserts a file
- K2 Image files are saved in images/, and one no note uses is cleaned up
- K3 An image taken out of a note is kept while undo can bring it back
- K4 An image in a table cell counts as in use

## L. Tables

- L1 Table (the toolbar or /table) adds a 3 × 3 table with a header row and the cursor in its first cell (U5)
- L2 A click right of a cell's text puts the cursor at its end
- L3 A drag selects in a cell, and a double click selects a word
- L4 Tab and Shift+Tab go to the next or previous cell; Tab past the last cell adds a row and goes to its first cell
- L5 Tab on a list item in a cell indents it
- L6 Enter makes a new line in a cell, not a row, and the table grows
- L7 Up and Down at a cell's first or last row go to the cell above or below, or out of the table; Esc leaves it
- L8 The arrows go into a table from the lines around it: the first cell from above, the last from below
- L9 Down from a table last in an expand goes below the expand, as in Confluence (U18)
- L10 A cell's right-click menu inserts rows and columns and deletes them or the table; a column added takes typing; deleting the last row or column deletes the table
- L10a Deleting the header row makes the next row the header. Unlike Confluence the table keeps a header, which a Markdown table must have (U6)
- L11 A deleted table comes back with Ctrl+Z, and takes clicks
- L12 Ctrl+Z in a cell undoes that cell's edits
- L13 A cell holds lists, quotes, code blocks, and formats
- L14 The toolbar and the shortcuts act on the cell with the cursor
- L15 A column is as wide as its text
- L16 Short inline code, as `x | y`, does not wrap in a narrow column
- L17 The header row is shaded and bold, and bold turns off in it; typing in a new table's header starts bold (U4, U5)
- L18 A note has one selection: a double click in a cell, then a click elsewhere, leaves no selection behind
- L19 Typing or Backspace over a selection across a table removes it without a crash, and Ctrl+Z brings it back
- L20 Backspace at the start of the line below a table goes into its last cell, or takes that line away when empty; Delete at the end of the line above selects the table, which typing replaces, as in Confluence
- L21 A click right of a table puts the cursor beside it, not in a cell; typing there goes on the line after it, as in Confluence
- L21b Beside a table, Enter opens a line after it, Backspace goes into the last cell, and Left goes into the table
- L22 Find finds text in cells, and Esc leaves the match selected in its cell
- L23 A folded expand hides a table in it
- L24 A table copies as a GitHub Markdown table: `<br>` for a line break in a cell, `\|` for a pipe, inline code as it is
- L25 A pasted Markdown table becomes a table, `<br>` a line of a cell, with the cells' formats
- L26 Markdown pasted into a cell keeps its formats; a table pasted in a cell goes after its table, which stays whole
- L27 A table in the 1.13 format, rows of tab-separated text, opens as a table (R4)
- L28 A cell's right-click opens one menu (T8)

## M. Expands

- M1 Expand (＋ or /expand) puts the selected lines in it; inserted on the last line, a line follows it
- M2 A click on the arrow, or Ctrl+Enter on the title, folds or opens it; folding moves a cursor inside to the title
- M3 An expand holds code blocks, lists, tables, and other expands
- M4 Enter on an empty line of an expand makes another line in it, as in Confluence (U11)
- M5 Backspace after an expand takes an empty line into it; Delete at the end of its last line takes the line after into it, as in Confluence
- M6 Backspace at the title's start keeps what it holds
- M7 In a note of 1.x, an expand never ended gets an end, and an end without one is taken out (tests/test_convert.py)
- M8 A find match in a folded expand opens it (T13)
- M9 An expand copies as `<details>` and pastes back as an expand (V8)

## N. Clipboard

- N1 Copied text goes to other apps as Markdown: headings, bold, inline code, fenced code, list levels, to-dos, quotes, dividers, tables, expands (V1)
- N2 Code alone is copied as it is, without fences (V2)
- N3 A paste into another note keeps everything as it was (V3)
- N4 Once another app takes the clipboard, its text is pasted, not Ynote's copy (V4)
- N5 Markdown from another app pastes in with its formats, and links as their text and address
- N6 A heading or code block pasted after text starts a line of its own
- N7 Ctrl+Shift+V pastes the text alone, without reading Markdown (V7)
- N8 Cut and paste brings everything back, tables included (V8)
- N9 Copying out and pasting back as Markdown gives the same note, but for a blank line before a divider
- N10 Names with underscores and lone stars stay text; inline code holding a backtick gets longer backticks

## O. Undo and redo

- O1 Ctrl+Z puts the cursor where the edit was
- O2 A table's changes and cell edits are steps of the note's undo (L11, L12)
- O3 After undo, the toolbar follows the formats at the cursor

## P. Search

- P1 Ctrl+F opens find, with Match case, regular expression, and All notes as last set (U21)
- P2 With All notes off, only this note is searched (T12)
- P3 Find ignores case and takes the query literally, unless Match case or .* is on
- P4 All notes lists each match with its note's title and the line, cut around the match; a hidden note's is tagged so
- P5 Enter goes to the next match (T12)
- P6 Choosing a match in All notes shows its note, a hidden one too (U16)
- P7 Highlights go when the search closes
- P8 Esc closes find, leaving the match selected (T12)

## Q. Drawing and wrapping [px]

- Q1 A long line wraps at the note's width; a code block's lines do not (I2)
- Q2 In a note with Korean, every line is as far from the next
- Q10 After Enter in a list, quote, code block, or table, and any key the note handles, the new line is in view
- Q11 Bold in a heading is drawn bolder, in English and Korean

## R. Notes from Ynote 1.x

- R1 Inline code padded by older versions opens as code
- R2 Lists indented by spaces open nested
- R4 Tables of tab-separated rows (1.13) become tables of cells
- R5 A note saved without newer fields (color, opacity, collapsed...) gets their defaults

## S. Korean through an input method

Typed through ibus with its Korean engine, as on a Korean desktop.

- S1 Korean is saved as composed: space and Enter end a syllable, and Backspace in one takes its last jamo
- S2 Enter while composing in a list item ends the syllable and starts the next item
- S3 Markdown typed around Korean, as `**굵게**` or `` `코드` ``, makes it bold or code
- S4 Ctrl+B while composing keeps the syllable as it was and bolds what follows
- S5 Korean typed into a table cell, empty or selected by Tab, stays on the cell's line
- S6 Korean typed into an expand's title and content stays where it is typed

## T. A note's bars, menus, and find

Its menus show in a popup window of their own, so they may reach past the
note.

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
- T18 Hidden notes, in the note menu (or the tray), lists them latest hidden first, each on its own color, and choosing one shows it (1.x's arrows to reorder them are gone: the latest hidden first is the order, and Find's All notes finds any)
- T19 Show all shows every hidden note
- T21 Collapse leaves the note as tall as its title bar, and Expand brings back its height (GNOME made a collapsed note 1px tall, from what its web view asks for; openbox, which the tests run, sized it right either way, so this test does not catch that bug)
- T22 A click outside closes the shortcuts, as any menu, and does nothing else; a note whose menu is open closes it when another window takes the focus
- T23 The note menu starts with New note and Hidden notes, which have no button, and ends with Delete, away from a quick click
- T24 A wheel notch scrolls as far as in 1.x, about the view's height to the 2/3 power, and at once: WebKit's animated scroll, drawn in software, lagged on the desktop (Xvfb does not animate it, so the test does not catch that)
- T25 Find's All notes stays where it is as it is turned on and off, beside Close
- T26 A menu, the shortcuts, or the hidden notes close when another window becomes active, as a click on another app on a Wayland desktop makes it, which Ynote never sees
- T20 F1 shows the keyboard shortcuts, made from the actions, with Ynote's version and where its notes are

## U. Editing

Where Ynote 2.0 follows Confluence over 1.x, the item says so.

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
- U25 A drag over a table shows what it selects while dragging, not only once let go
- U26 Right at the very end of a code block puts the cursor after it: on the line there, or, with none, as before a divider or a table, where Enter or typing makes one, as in Confluence
- U27 Right at the very end of a table does the same
- U19 // where a word starts types today's date, as in Confluence
- U20 // after other text, as in https://, stays as typed

## V. Copy and paste

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

## X. A note among other windows

- X1 A note on top stays above another app's window [WM]
- X2 Alt+scroll steps through the notes from the latest used [WM]
- X3 Scrolling back while Alt is held retraces the steps [WM]
- X4 A quick second scroll is one step
- X5 A hidden note shows again where it was
- X6 Alt+scroll brings up stacked notes one after another, as in 1.x [WM] (right after a start, with another app focused, GNOME left the note behind when presented at the scroll's time; it is now presented at the X server's time, which openbox, which the tests run, does not need)
- X7 Letting go of Alt gives the note Alt+scroll stopped on the focus, as Alt+Tab does: GNOME brings a note forward while Alt is held but keeps the focus where it was (openbox focuses it at once, so the test does not catch that)
- X8 The first Alt+scroll after a start steps too: GTK on X11 gives the first smooth scroll no amount, which counts as a notch the way the last one went, down at first (tested on GNOME, X9: Xvfb gives the amount)
- X9 Every Alt+scroll notch steps, also the first after a start and the first after a note comes up under the pointer [GNOME] (GTK starts measuring scrolls over as the pointer comes into a window, and gives the first no amount, marked as a stop: that was taken for a touchpad's stop and dropped, so every other notch did nothing, and the notes seemed to come up out of order)
- X10 Letting go of Alt leaves the note stepped to active and on top [GNOME]
