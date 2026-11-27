"""A table whose cells are editors, set in a note's text the way an image is.

Each cell is a CellEditor: an Editor of its own, so it holds several lines,
lists, quotes, code blocks, inline formats, and images, all edited as in a
note. The note keeps the table at a child anchor, and saves its rows of cells
in its `tables` field, each cell as the text and formats a rich state holds.
"""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango

from .editor import TEXT_MARGIN, Editor
from .config import IMAGE_ANCHOR
from .styles import (
    CODE_FONT, CODE_OUTLINE, HEADING_FONT, HEADING_SCALE, TABLE_MARGIN)

# How narrow a column can get, in em, so an empty one can still be clicked.
MIN_COLUMN_EM = 3


def empty_cell():
    return {'text': '', 'bold': [], 'heading': [], 'code': [],
            'backtick': [], 'images': []}


class _NoScroll:
    """What a cell has in place of a scrolled window: the editor asks one
    for its scroll position around undo, and a cell has none of its own."""

    def __init__(self):
        self._adjustment = Gtk.Adjustment()

    def get_vadjustment(self):
        return self._adjustment


class CellEditor(Editor):
    """One cell of a table. It takes the note's font size and colors, saves
    with the note, and tells the note which editor the Format and Insert
    menus act on."""

    def __init__(self, table, state):
        self.table = table
        self.note = table.note
        self.app = self.note.app
        self._sw = _NoScroll()
        self._build_editor({
            'text': state.get('text', ''),
            'bold_ranges': state.get('bold', []),
            'heading_ranges': state.get('heading', []),
            'code_ranges': state.get('code', []),
            'backtick_ranges': state.get('backtick', []),
            'images': state.get('images', []),
        })
        # A cell's text wraps at the width of its column.
        self.tv.set_hexpand(False)
        self.tv.connect('focus-in-event', self._on_focus_in)
        self.tv.get_buffer().connect('changed', self._on_changed)
        # A click in a cell ends there once the cell has placed its cursor.
        # A text view passes it on to the one it is in, the note's, which
        # would put its own cursor at the table and so enter the first cell.
        for signal in ('button-press-event', 'button-release-event'):
            self.tv.connect_after(signal, lambda *_: True)

    # What the editor reads from its owner is the note's.
    @property
    def _font_size(self):
        return self.note._font_size

    @property
    def _opacity(self):
        return self.note._opacity

    @property
    def _code_rgba(self):
        return self.note._code_rgba

    @property
    def _inline_rgba(self):
        return self.note._inline_rgba

    @property
    def _body_rgba(self):
        return self.note._body_rgba

    def get_scale_factor(self):
        return self.note.get_scale_factor()

    def _toggle_search(self):
        # Search, from a cell's right-click menu, is the note's.
        self.note._toggle_search()

    def _queue_save(self):
        self.note._on_table_changed()

    def _refresh_format_buttons(self):
        if self.note._active_editor() is self:
            self.note._refresh_format_buttons()

    def _sync_format_state(self):
        super()._sync_format_state()
        self._header_bold_by_default()

    def _after_buf_insert_text(self, buf, location, text, length):
        super()._after_buf_insert_text(buf, location, text, length)
        if text.startswith('\n'):
            self._header_bold_by_default()

    def _header_bold_by_default(self):
        """A header cell is bold until bold is turned off in it, also on a
        line that has no text yet to take bold from."""
        cells = getattr(self.table, 'cells', None)
        buf = self.tv.get_buffer()
        if (not cells or self not in cells[0] or self._pending_format_inserts
                or buf.get_has_selection()):
            return
        line = buf.get_iter_at_mark(buf.get_insert()).get_line()
        if self._line_bounds(line)[0].ends_line():
            self._bold_active = True
            self._refresh_format_buttons()

    def _on_focus_in(self, *_):
        self.note._set_active_editor(self)
        return False

    def _on_changed(self, _buf):
        if not self._restoring:
            self.table.queue_widths()

    def state(self):
        """The cell's text and formats, as saved."""
        state = self._current_state()
        return {key: state[key] for key in
                ('text', 'bold', 'heading', 'code', 'backtick', 'images')}

    def _convert_text_tables(self):
        # A table is not put in a cell.
        return False

    def natural_line_width(self, start, end):
        """How wide the text from start to end is on one row, each run of
        it in the font its formats give. Inline code is in the code font and
        has a padding space at each end, so measured as body text it would
        come out narrower, and its column would wrap it."""
        width = 0
        it = start.copy()
        while it.compare(end) < 0:
            run_end = it.copy()
            if (not run_end.forward_to_tag_toggle(None)
                    or run_end.compare(end) > 0):
                run_end = end.copy()
            width += self._run_width(it, run_end)
            it = run_end
        return width

    def _run_width(self, start, end):
        # An image is measured by its widget, apart from the text.
        text = start.get_slice(end).replace(IMAGE_ANCHOR, '')
        if not text:
            return 0
        font = self._body_font.copy()
        scale = 1.0
        if start.has_tag(self._heading_tag):
            font.set_family(HEADING_FONT)
            font.set_weight(Pango.Weight.BOLD)
            scale = HEADING_SCALE
        elif start.has_tag(self._backtick_tag):
            font.set_family(CODE_FONT)
            scale = self._backtick_tag.get_property('scale')
        if start.has_tag(self._bold_tag):
            font.set_weight(Pango.Weight.BOLD)
        return self._text_width(font, text, scale)

    # -------------------------------------------------------------- keys

    def _handle_tv_key(self, tv, event):
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        keyval = event.keyval
        buf = tv.get_buffer()
        if (keyval in (Gdk.KEY_Tab, Gdk.KEY_KP_Tab, Gdk.KEY_ISO_Left_Tab)
                and state in (0, Gdk.ModifierType.SHIFT_MASK)
                and not self._line_has_list_marker(
                    buf.get_iter_at_mark(buf.get_insert()).get_line())):
            # Tab indents a list item in a cell as anywhere, and otherwise
            # goes to the next cell; past the last one it adds a row.
            forward = state == 0 and keyval != Gdk.KEY_ISO_Left_Tab
            self.table.step(self, forward)
            return True
        if state == 0 and keyval == Gdk.KEY_Escape:
            self.table.leave(forward=True)
            return True
        if state == 0 and keyval in (Gdk.KEY_Up, Gdk.KEY_Down):
            # On the cell's first row of text, Up goes to the cell above, and
            # on its last, Down to the cell below: a row of text is where its
            # characters are drawn at the same height.
            down = keyval == Gdk.KEY_Down
            cursor = buf.get_iter_at_mark(buf.get_insert())
            edge = buf.get_end_iter() if down else buf.get_start_iter()
            if tv.get_iter_location(cursor).y == tv.get_iter_location(edge).y:
                self.table.step_vertical(self, down)
                return True
        return super()._handle_tv_key(tv, event)

    # -------------------------------------------------------------- menu

    def _on_tv_popup(self, view, menu):
        super()._on_tv_popup(view, menu)
        row, column = self.table.position(self)
        items = [
            ('Add Row Below', lambda: self.table.add_row(row)),
            ('Add Column Right', lambda: self.table.add_column(column)),
            ('Delete Row', lambda: self.table.delete_row(row)),
            ('Delete Column', lambda: self.table.delete_column(column)),
            ('Delete Table', self.table.delete),
        ]
        menu.prepend(Gtk.SeparatorMenuItem())
        for label, action in reversed(items):
            item = Gtk.MenuItem(label=label)
            item.connect('activate', lambda _, act=action: act())
            menu.prepend(item)
        menu.show_all()


class TableWidget(Gtk.Grid):
    """The cells of a table in rows, with its lines and shaded header drawn
    around them. Its columns are as wide as their widest text, shrunk to fit
    the note when they would not."""

    def __init__(self, note, rows, anchor):
        super().__init__()
        self.note = note
        self.anchor = anchor
        self.set_margin_top(TABLE_MARGIN)
        self.set_margin_bottom(TABLE_MARGIN)
        self.set_halign(Gtk.Align.START)
        self.cells = [[CellEditor(self, cell) for cell in row]
                      for row in (rows or [[empty_cell()]])]
        self._widths_sid = None
        self.connect('draw', self._draw_header)
        self.connect_after('draw', self._draw_lines)
        self._lay_out()
        self.show()
        # Shown and hidden by the note alone, as a folded expand hides it.
        self.set_no_show_all(True)

    # -------------------------------------------------------------- state

    def all_cells(self):
        return [cell for row in self.cells for cell in row]

    def rows_state(self):
        return [[cell.state() for cell in row] for row in self.cells]

    def text(self):
        """The text of every cell, for searching all notes."""
        return '\n'.join(cell.tv.get_buffer().get_slice(
            cell.tv.get_buffer().get_start_iter(),
            cell.tv.get_buffer().get_end_iter(), True)
            for cell in self.all_cells())

    def position(self, cell):
        for r, row in enumerate(self.cells):
            if cell in row:
                return r, row.index(cell)
        return 0, 0

    # -------------------------------------------------------------- layout

    def _lay_out(self):
        for child in self.get_children():
            self.remove(child)
        for r, row in enumerate(self.cells):
            for c, cell in enumerate(row):
                self.attach(cell.tv, c, r, 1, 1)
                # Each cell is shown itself: the table's show_all() does
                # nothing, since the note alone shows and hides the table.
                cell.tv.show_all()
        self.queue_widths()

    def queue_widths(self):
        if self._widths_sid is None:
            self._widths_sid = GLib.idle_add(self._set_widths)

    def _set_widths(self):
        self._widths_sid = None
        columns = max(len(row) for row in self.cells)
        least = MIN_COLUMN_EM * self.note._font_size
        natural = [least] * columns
        for row in self.cells:
            for c, cell in enumerate(row):
                natural[c] = max(natural[c], self._natural_width(cell))
        room = max(columns * least, self.note.tv.get_allocated_width()
                   - 2 * TEXT_MARGIN - 2)
        total = sum(natural)
        if total > room:
            widths = [max(least, int(n * room / total)) for n in natural]
        else:
            widths = natural
        for row in self.cells:
            for c, cell in enumerate(row):
                cell.tv.set_size_request(widths[c], -1)
        return False

    @staticmethod
    def _natural_width(cell):
        """How wide the cell's text is on one line: its longest line, and
        any image in it, with the cell's margins."""
        buf = cell.tv.get_buffer()
        widest = 0
        for line in range(buf.get_line_count()):
            start, end = cell._line_bounds(line)
            if cell._is_code_line(buf, line):
                # Code does not wrap, so its line is as wide as it is laid
                # out, in the code font.
                width = cell.tv.get_iter_location(end).x - TEXT_MARGIN
            else:
                width = cell.natural_line_width(start, end) * 1.08
            it = start.copy()
            while it.compare(end) < 0:
                anchor = it.get_child_anchor()
                if anchor is not None:
                    width += max((w.get_preferred_width()[1]
                                  for w in anchor.get_widgets()), default=0)
                it.forward_char()
            widest = max(widest, width)
        return int(widest) + 2 * TEXT_MARGIN + 4

    # -------------------------------------------------------------- drawing

    def _cell_rects(self):
        rects = []
        for r, row in enumerate(self.cells):
            for c, cell in enumerate(row):
                a = cell.tv.get_allocation()
                rects.append((r, c, a.x - self.get_allocation().x,
                              a.y - self.get_allocation().y,
                              a.width, a.height))
        return rects

    def _draw_header(self, _widget, cr):
        head = self.note._code_rgba
        cr.set_source_rgba(head.red, head.green, head.blue, 1.0)
        for r, _c, x, y, w, h in self._cell_rects():
            if r == 0:
                cr.rectangle(x, y, w, h)
        cr.fill()
        if self.note._opacity < 1.0:
            # Opaque behind the text, as text in a see-through note is.
            body = self.note._body_rgba
            cr.set_source_rgba(body.red, body.green, body.blue, 1.0)
            for r, _c, x, y, w, h in self._cell_rects():
                if r > 0:
                    cr.rectangle(x, y, w, h)
            cr.fill()
        return False

    def _draw_lines(self, _widget, cr):
        # Each cell draws the line on its left and above it, and the table
        # the one on its right and below it, so no line is drawn twice.
        cr.set_source_rgba(*CODE_OUTLINE)
        cr.set_line_width(1)
        right = bottom = 0
        for _r, _c, x, y, w, h in self._cell_rects():
            cr.move_to(x + 0.5, y + h)
            cr.line_to(x + 0.5, y + 0.5)
            cr.line_to(x + w, y + 0.5)
            right, bottom = max(right, x + w), max(bottom, y + h)
        cr.move_to(right - 0.5, 0)
        cr.line_to(right - 0.5, bottom - 0.5)
        cr.line_to(0, bottom - 0.5)
        cr.stroke()
        return False

    # -------------------------------------------------------------- moving

    def focus_cell(self, row, column, at_end=True):
        cell = self.cells[row][column]
        buf = cell.tv.get_buffer()
        buf.place_cursor(buf.get_end_iter() if at_end
                         else buf.get_start_iter())
        cell.tv.grab_focus()
        # Also when the window does not have the focus to give the cell.
        self.note._set_active_editor(cell)

    def step(self, cell, forward):
        r, c = self.position(cell)
        columns = len(self.cells[r])
        if forward:
            if c + 1 < columns:
                self.focus_cell(r, c + 1)
            elif r + 1 < len(self.cells):
                self.focus_cell(r + 1, 0)
            else:
                self.add_row(r)
        elif c > 0:
            self.focus_cell(r, c - 1)
        elif r > 0:
            self.focus_cell(r - 1, len(self.cells[r - 1]) - 1)

    def step_vertical(self, cell, down):
        r, c = self.position(cell)
        target = r + (1 if down else -1)
        if 0 <= target < len(self.cells):
            self.focus_cell(target, min(c, len(self.cells[target]) - 1),
                            at_end=not down)
        else:
            self.leave(forward=down)

    def leave(self, forward):
        """Put the cursor in the note's text, after the table or before it."""
        self.note._leave_table(self, forward)

    # -------------------------------------------------------------- editing

    def _changed_structure(self, focus=None):
        self._lay_out()
        self.note._on_table_changed()
        if focus is not None:
            GLib.idle_add(lambda: self.focus_cell(*focus) and False)

    def add_row(self, after):
        columns = max(len(row) for row in self.cells)
        self.cells.insert(after + 1, [CellEditor(self, empty_cell())
                                      for _ in range(columns)])
        self._changed_structure(focus=(after + 1, 0, False))

    def add_column(self, after):
        for row in self.cells:
            row.insert(after + 1, CellEditor(self, empty_cell()))
        self._changed_structure(focus=(0, after + 1, False))

    def delete_row(self, row):
        if len(self.cells) == 1:
            self.delete()
            return
        del self.cells[row]
        if row == 0:
            # The next row becomes the header, which is bold until bold is
            # turned off in it. A Markdown table always has one.
            for cell in self.cells[0]:
                buf = cell.tv.get_buffer()
                text = buf.get_slice(buf.get_start_iter(),
                                     buf.get_end_iter(), True)
                for start, end in Editor._line_ranges(text):
                    buf.apply_tag(cell._bold_tag, buf.get_iter_at_offset(start),
                                  buf.get_iter_at_offset(end))
        self._changed_structure(
            focus=(min(row, len(self.cells) - 1), 0, True))

    def delete_column(self, column):
        if max(len(row) for row in self.cells) == 1:
            self.delete()
            return
        for row in self.cells:
            if column < len(row):
                del row[column]
        self._changed_structure(
            focus=(0, min(column, len(self.cells[0]) - 1), True))

    def delete(self):
        self.note._delete_table(self)
