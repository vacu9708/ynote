"""A table whose cells are editors: each cell keeps its text and formats,
Tab moves between cells and adds a row past the last, Enter starts a new line
in a cell, and rows and columns are added and deleted."""
from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

from ynote.table import TableWidget, empty_cell


class FakeNote:
    """What a table asks of the note it is in."""

    def __init__(self):
        self.app = None
        self._font_size = 14
        self._opacity = 1.0
        self._code_rgba = self._inline_rgba = self._body_rgba = Gdk.RGBA()
        self.tv = Gtk.TextView()
        self.active = None
        self.changes = 0
        self.left = None
        self.deleted = False

    def get_scale_factor(self):
        return 1

    def _active_editor(self):
        return self.active

    def _set_active_editor(self, editor):
        self.active = editor

    def _refresh_format_buttons(self):
        pass

    def _on_table_changed(self):
        self.changes += 1

    def _leave_table(self, table, forward):
        self.left = forward

    def _delete_table(self, table):
        self.deleted = True


def cell(text, **ranges):
    return dict(empty_cell(), text=text, **ranges)


def make_table(rows):
    return TableWidget(FakeNote(), rows, anchor=None)


def text_of(editor):
    buf = editor.tv.get_buffer()
    return buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)


def press(editor, keyval, state=0):
    return editor._on_tv_key_press(
        editor.tv, SimpleNamespace(state=state, keyval=keyval))


def test_each_cell_keeps_its_text_and_formats():
    rows = [[cell('Name', bold=[[0, 4]]), cell('Notes')],
            [cell('Kim'), cell('first\nsecond')]]

    table = make_table(rows)

    assert [[c['text'] for c in row] for row in table.rows_state()] == [
        ['Name', 'Notes'], ['Kim', 'first\nsecond']]
    assert table.rows_state()[0][0]['bold'] == [[0, 4]]


def test_tab_goes_to_the_next_cell_and_past_the_last_adds_a_row():
    table = make_table([[cell('a'), cell('b')]])
    first, second = table.cells[0]

    assert press(first, Gdk.KEY_Tab)
    assert table.note.active is second

    press(second, Gdk.KEY_Tab)
    assert len(table.cells) == 2
    assert table.note.changes == 1


def test_shift_tab_goes_to_the_cell_before():
    table = make_table([[cell('a'), cell('b')]])

    press(table.cells[0][1], Gdk.KEY_ISO_Left_Tab, Gdk.ModifierType.SHIFT_MASK)

    assert table.note.active is table.cells[0][0]


def test_enter_in_a_cell_is_left_to_the_editor_as_a_new_line():
    table = make_table([[cell('a')]])

    assert not press(table.cells[0][0], Gdk.KEY_Return)


def test_escape_leaves_the_table_forward():
    table = make_table([[cell('a')]])

    assert press(table.cells[0][0], Gdk.KEY_Escape)
    assert table.note.left is True


def test_rows_and_columns_are_added_and_deleted():
    table = make_table([[cell('a'), cell('b')], [cell('c'), cell('d')]])

    table.add_column(0)
    assert [[c['text'] for c in row] for row in table.rows_state()] == [
        ['a', '', 'b'], ['c', '', 'd']]
    table.delete_row(0)
    assert [[c['text'] for c in row] for row in table.rows_state()] == [
        ['c', '', 'd']]
    table.delete_column(2)
    assert [[c['text'] for c in row] for row in table.rows_state()] == [
        ['c', '']]


def test_deleting_the_last_row_deletes_the_table():
    table = make_table([[cell('a')]])

    table.delete_row(0)

    assert table.note.deleted
