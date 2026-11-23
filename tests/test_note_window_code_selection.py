"""Clearing a selection must not raise from the buffer's mark-set handler.

An unhandled exception there made Ubuntu's apport build a crash report on
the UI thread, which froze the note for a moment on every click that cleared
a selection."""
import types

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.note_window import NoteWindow


class FakeStyleContext:
    def __init__(self):
        self.classes = set()

    def add_class(self, name):
        self.classes.add(name)

    def remove_class(self, name):
        self.classes.discard(name)


class FakeTextView:
    def __init__(self):
        self.context = FakeStyleContext()

    def get_style_context(self):
        return self.context

    def queue_draw(self):
        pass

    def get_left_margin(self):
        return 6

    def get_iter_location(self, it):
        # A monospace column is 10 px wide.
        return types.SimpleNamespace(x=6 + 10 * it.get_line_offset())


def make_window():
    buf = Gtk.TextBuffer()
    code = buf.create_tag('code')
    buf.set_text('prose\ncode one\ncode two\ncode three\nprose')
    buf.apply_tag(code, buf.get_iter_at_line(1), buf.get_iter_at_line(4))
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView()
    win._code_tag = code
    win._hl_tag = buf.create_tag('hl')
    win._code_selection = None
    win._code_block_cache = {}
    win._watch_code_blocks(buf)
    win.tv.get_buffer = lambda: buf
    errors = []

    def on_mark_set(buf, it, mark):
        try:
            win._refresh_code_selection(buf)
        except Exception as error:
            errors.append(error)

    buf.connect('mark-set', on_mark_set)
    return win, buf, errors


def test_clearing_a_selection_does_not_raise():
    win, buf, errors = make_window()

    buf.select_range(buf.get_iter_at_line(0), buf.get_iter_at_line(2))
    buf.place_cursor(buf.get_iter_at_line(4))

    assert errors == []


def test_multi_line_code_selection_is_tracked_and_cleared():
    win, buf, errors = make_window()

    buf.select_range(buf.get_iter_at_line(1), buf.get_iter_at_line(3))
    assert win._code_selection is not None
    assert 'code-selection' in win.tv.context.classes

    buf.place_cursor(buf.get_iter_at_line(0))
    assert win._code_selection is None
    assert 'code-selection' not in win.tv.context.classes
    assert errors == []
