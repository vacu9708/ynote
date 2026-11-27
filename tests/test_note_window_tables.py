"""A table is rows of cells: a row is a line that starts with TABLE_MARKER and
has its cells separated by tabs. Tab moves between cells, Enter adds a row,
and Backspace or Delete never take the tab between two cells. ¶ stands for the
marker and → for a tab in the text of these tests."""
from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

from ynote.config import TABLE_MARKER
from ynote.note_window import NoteWindow


def tb(text):
    return text.replace('¶', TABLE_MARKER).replace('→', '\t')


def shown(buf):
    text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
    return text.replace(TABLE_MARKER, '¶').replace('\t', '→')


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf

    def get_buffer(self):
        return self._buf

    def scroll_mark_onscreen(self, mark):
        pass


def make_window(text, cursor=0):
    buf = Gtk.TextBuffer()
    buf.set_text(tb(text))
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    for name in ('code', 'heading', 'bold', 'backtick'):
        setattr(win, f'_{name}_tag', buf.create_tag(name))
    win._divider_lines = []
    win._snap_sid = None
    win._pending_format_inserts = []
    win._restoring = False
    win._flush_snapshot = lambda: None
    win._queue_save = lambda: None
    win._sync_format_state = lambda: None
    win._refresh_line_styles = lambda: None
    win._queue_code_margins = lambda: None
    buf.place_cursor(buf.get_iter_at_offset(cursor))
    return win, buf


def cursor(buf):
    return buf.get_iter_at_mark(buf.get_insert()).get_offset()


def press(win, keyval, state=0):
    return win._on_tv_key_press(
        win.tv, SimpleNamespace(state=state, keyval=keyval))


# Offsets: ¶ 0, "ab" 1..3, → 3, "c" 4, \n 5, ¶ 6, "d" 7, → 8, "" 9.
TABLE = '¶ab→c\n¶d→'


def test_tab_goes_to_the_end_of_the_next_cell():
    win, buf = make_window(TABLE, cursor=2)

    assert press(win, Gdk.KEY_Tab)

    assert cursor(buf) == 5
    assert shown(buf) == TABLE


def test_tab_from_the_last_cell_of_a_row_goes_to_the_next_row():
    win, buf = make_window(TABLE, cursor=5)

    press(win, Gdk.KEY_Tab)

    assert cursor(buf) == 8


def test_tab_from_the_last_cell_adds_a_row():
    win, buf = make_window(TABLE, cursor=9)

    press(win, Gdk.KEY_Tab)

    assert shown(buf) == '¶ab→c\n¶d→\n¶→'
    assert cursor(buf) == 11


def test_shift_tab_goes_to_the_cell_before():
    win, buf = make_window(TABLE, cursor=7)

    press(win, Gdk.KEY_ISO_Left_Tab, Gdk.ModifierType.SHIFT_MASK)

    assert cursor(buf) == 5


def test_enter_adds_a_row_after_the_cursors_row():
    win, buf = make_window(TABLE, cursor=2)

    assert press(win, Gdk.KEY_Return)

    assert shown(buf) == '¶ab→c\n¶→\n¶d→'
    assert cursor(buf) == 7


def test_enter_on_an_empty_last_row_ends_the_table():
    win, buf = make_window('¶ab→c\n¶→', cursor=7)

    press(win, Gdk.KEY_Return)

    assert shown(buf) == '¶ab→c\n'
    assert cursor(buf) == 6


def test_enter_at_the_start_of_the_table_adds_a_line_before_it():
    win, buf = make_window(TABLE, cursor=1)

    press(win, Gdk.KEY_Return)

    assert shown(buf) == '\n' + TABLE
    assert cursor(buf) == 0


def test_backspace_and_delete_never_take_the_tab_between_cells():
    win, buf = make_window(TABLE, cursor=4)
    assert press(win, Gdk.KEY_BackSpace)
    buf.place_cursor(buf.get_iter_at_offset(3))
    assert press(win, Gdk.KEY_Delete)

    assert shown(buf) == TABLE


def test_backspace_inside_a_cell_is_left_to_gtk():
    win, buf = make_window(TABLE, cursor=2)

    assert not press(win, Gdk.KEY_BackSpace)


def test_backspace_at_the_start_of_an_empty_row_deletes_it():
    win, buf = make_window('¶ab→c\n¶→\n¶d→', cursor=7)

    press(win, Gdk.KEY_BackSpace)

    assert shown(buf) == '¶ab→c\n¶d→'
    assert cursor(buf) == 5


def test_delete_at_the_end_of_a_line_before_a_table_keeps_the_table():
    win, buf = make_window('text\n' + TABLE, cursor=4)

    assert press(win, Gdk.KEY_Delete)


def test_rows_get_as_many_cells_as_the_widest():
    win, buf = make_window('¶a→b→c\n¶d')
    win._normalizing = False

    assert win._normalize_tables()

    assert shown(buf) == '¶a→b→c\n¶d→→'


def test_a_marker_joined_into_a_line_is_taken_out():
    win, buf = make_window('text¶a→b')
    win._normalizing = False

    win._normalize_tables()

    assert shown(buf) == 'texta→b'


def test_add_column_adds_a_cell_after_the_cursors_in_every_row():
    win, buf = make_window(TABLE, cursor=2)

    win._add_table_column()

    assert shown(buf) == '¶ab→→c\n¶d→→'
    assert cursor(buf) == 4


def test_delete_column_takes_the_cursors_cell_from_every_row():
    win, buf = make_window(TABLE, cursor=4)

    win._delete_table_column()

    assert shown(buf) == '¶ab\n¶d'


def test_insert_table_on_an_empty_line_puts_the_cursor_in_its_first_cell():
    win, buf = make_window('text\n', cursor=5)

    win._insert_table(columns=2, rows=2)

    assert shown(buf) == 'text\n¶→\n¶→\n'
    assert cursor(buf) == 6


def test_a_row_is_not_a_list_item_heading_or_code_line():
    win, buf = make_window('¶• a→b', cursor=3)

    assert win._marker_end(0) == 1
    assert win._heading_lines() == []
    assert win._line_list_parts(0) is None
