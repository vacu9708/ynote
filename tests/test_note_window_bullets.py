from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

from ynote.note_window import NoteWindow


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf

    def get_buffer(self):
        return self._buf


def make_window_with_buffer(text):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    win._code_tag = buf.create_tag('code')
    return win, buf


def press_enter_at(text, offset):
    win, buf = make_window_with_buffer(text)
    buf.place_cursor(buf.get_iter_at_offset(offset))

    handled = win._on_tv_key_press(
        win.tv,
        SimpleNamespace(state=0, keyval=Gdk.KEY_Return))

    cursor = buf.get_iter_at_mark(buf.get_insert())
    text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
    return handled, text, cursor.get_offset()


def test_enter_at_start_of_bullet_inserts_clean_bullet_above():
    handled, text, cursor_offset = press_enter_at('• item', 0)

    assert handled is True
    assert text == '• \n• item'
    assert cursor_offset == 2


def test_enter_inside_bullet_marker_inserts_clean_bullet_above():
    handled, text, cursor_offset = press_enter_at('• item', 1)

    assert handled is True
    assert text == '• \n• item'
    assert cursor_offset == 2


def test_enter_in_bullet_body_still_splits_current_item():
    handled, text, cursor_offset = press_enter_at('• item', 4)

    assert handled is True
    assert text == '• it\n• em'
    assert cursor_offset == 7
