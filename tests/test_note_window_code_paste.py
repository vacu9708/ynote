import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.config import CODE_ANCHOR
from ynote.note_window import NoteWindow


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf
        self.focused = False

    def get_buffer(self):
        return self._buf

    def grab_focus(self):
        self.focused = True


def make_window_with_buffer(text):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    win._code_tag = buf.create_tag('code')
    win._restoring = False
    win._refresh_emoji_tags = lambda: None
    win._take_snapshot = lambda: None
    win._queue_save = lambda: None
    return win, buf


def test_replacing_selected_code_block_keeps_code_formatting():
    win, buf = make_window_with_buffer('old code')
    start = buf.get_start_iter()
    end = buf.get_end_iter()
    buf.apply_tag(win._code_tag, start, end)
    buf.select_range(start, end)

    win._replace_selection_with_code_text('new code')

    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False) == 'new code'
    assert win._line_is_fully_tagged(win._code_tag, 0)
    assert win.tv.focused is True


def test_replacing_code_block_with_blank_line_keeps_blank_line_in_code_block():
    win, buf = make_window_with_buffer('old code')
    start = buf.get_start_iter()
    end = buf.get_end_iter()
    buf.apply_tag(win._code_tag, start, end)
    buf.select_range(start, end)

    win._replace_selection_with_code_text('first\n\nlast')

    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).replace(
        CODE_ANCHOR, '') == 'first\n\nlast'
    assert win._line_is_fully_tagged(win._code_tag, 0)
    assert win._line_is_fully_tagged(win._code_tag, 1)
    assert win._line_is_fully_tagged(win._code_tag, 2)
