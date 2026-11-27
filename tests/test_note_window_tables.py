"""A table in a real note: it goes away with text deleted over it, keeps each
cell's selection and whether a folded expand hides it when it is laid out
again, and is left past what the cursor skips, not back into it."""
from unittest.mock import MagicMock

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gio, Gtk

from ynote.config import EXPAND_END, EXPAND_OPEN, TABLE_MARKER
from ynote.note_window import NoteWindow


class FakeApp(Gtk.Application):
    """An application a note can be made in: whatever it is asked for is a
    stand-in."""

    def __getattr__(self, name):
        value = MagicMock(name=name)
        setattr(self, name, value)
        return value


_app = None


def make_note(lines):
    global _app
    if _app is None:
        _app = FakeApp(application_id='io.github.ynote.tests',
                       flags=Gio.ApplicationFlags.NON_UNIQUE)
        _app.register(None)
    note = NoteWindow(_app, {'id': 'n', 'text': '\n'.join(lines),
                             'w': 400, 'h': 400})
    settle()
    return note


def settle():
    while Gtk.events_pending():
        Gtk.main_iteration()


def table_row(*cells):
    return TABLE_MARKER + '\t'.join(cells)


def cursor(buf):
    return buf.get_iter_at_mark(buf.get_insert()).get_offset()


def test_text_deleted_over_a_table_takes_the_table_with_it():
    note = make_note(['above', table_row('a', 'b'), table_row('c', 'd'),
                      'below'])
    buf = note.tv.get_buffer()
    assert len(note._table_widgets) == 1

    # As typing over a selection from "above" into "below" deletes it.
    buf.select_range(buf.get_iter_at_offset(2),
                     buf.get_iter_at_offset(buf.get_char_count() - 2))
    buf.delete_selection(True, True)
    settle()

    assert note._table_widgets == []
    assert buf.get_slice(*buf.get_bounds(), True) == 'abow'


def test_leaving_a_table_skips_an_expands_end_the_way_it_leaves():
    note = make_note([EXPAND_OPEN + 'Title', table_row('a', 'b'), EXPAND_END,
                      'after'])
    buf = note.tv.get_buffer()
    table = note._table_widgets[0]
    # The note's cursor was last further down than the table.
    buf.place_cursor(buf.get_end_iter())
    settle()
    table.focus_cell(0, 1)
    settle()

    table.leave(forward=True)
    settle()

    assert note._active_editor() is note
    after = buf.get_slice(*buf.get_bounds(), True).index('after')
    assert cursor(buf) == after


def test_added_rows_and_columns_are_shown():
    note = make_note(['above', table_row('a', 'b')])
    table = note._table_widgets[0]

    table.add_row(0)
    table.add_column(1)
    settle()

    assert all(cell.tv.get_visible() for cell in table.all_cells())


def test_a_click_in_a_cell_stays_in_the_cell():
    note = make_note(['above', table_row('a', 'b')])
    table = note._table_widgets[0]
    note.show_all()
    settle()
    tv = table.cells[0][1].tv
    passed_on = []
    note.tv.connect('button-press-event',
                    lambda *_: passed_on.append(True) or False)

    event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    event.button.button = 1
    event.button.window = tv.get_window(Gtk.TextWindowType.TEXT)
    Gtk.propagate_event(tv, event)

    assert passed_on == []


def test_a_header_cell_is_bold_until_bold_is_turned_off():
    note = make_note(['above', table_row('Name', 'Age'), table_row('Kim', '3')])
    table = note._table_widgets[0]
    head, body = table.cells[0][0], table.cells[1][0]
    assert head.state()['bold'] == [[0, 4]]
    assert body.state()['bold'] == []

    table.add_column(1)
    settle()
    empty = table.cells[0][2]
    empty.tv.get_buffer().place_cursor(empty.tv.get_buffer().get_end_iter())
    empty._sync_format_state()
    assert empty._bold_active
    empty._toggle_bold()
    assert not empty._bold_active

    hbuf = head.tv.get_buffer()
    hbuf.select_range(hbuf.get_start_iter(), hbuf.get_end_iter())
    head._toggle_bold()
    assert head.state()['bold'] == []


def test_a_note_has_one_selection_across_its_text_and_cells():
    note = make_note(['above', table_row('Name', 'Age'), table_row('Kim', '3')])
    table = note._table_widgets[0]
    head = table.cells[0][0].tv.get_buffer()
    head.select_range(head.get_start_iter(), head.get_end_iter())
    note._set_active_editor(table.cells[0][0])

    table.focus_cell(1, 0)
    assert not head.get_has_selection()

    body = table.cells[1][0].tv.get_buffer()
    body.select_range(body.get_start_iter(), body.get_end_iter())
    note._set_active_editor(note)
    assert not body.get_has_selection()
