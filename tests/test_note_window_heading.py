"""Heading format on a NoteWindow built without a display or a GTK window."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.note_window import NoteWindow


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf

    def get_buffer(self):
        return self._buf

    def scroll_mark_onscreen(self, mark):
        pass


class FakeStyleContext:
    def __init__(self):
        self.classes = set()

    def add_class(self, name):
        self.classes.add(name)

    def remove_class(self, name):
        self.classes.discard(name)


class FakeButton:
    def __init__(self):
        self.context = FakeStyleContext()
        self.sensitive = True

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive

    def get_style_context(self):
        return self.context


def make_window(text, cursor=0):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    win._code_tag = buf.create_tag('code')
    win._bold_tag = buf.create_tag('bold')
    win._backtick_tag = buf.create_tag('backtick')
    win._heading_tag = buf.create_tag('heading')
    win._format_btn = FakeButton()
    win._divider_lines = []
    win._pending_format_inserts = []
    win._restoring = False
    win._snap_sid = None
    win._take_snapshot = lambda: None
    win._queue_save = lambda: None
    win._refresh_emoji_tags = lambda: None
    buf.place_cursor(buf.get_iter_at_offset(cursor))
    return win, buf


def type_text(win, buf, text):
    """Insert at the cursor through the same handlers typing goes through."""
    buf.connect('insert-text', win._on_buf_insert_text)
    buf.connect_after('insert-text', win._after_buf_insert_text)
    buf.insert_at_cursor(text)


def headed(win, buf):
    return win._get_tag_ranges(win._heading_tag)


def test_heading_covers_the_cursor_line_without_its_newline():
    win, buf = make_window('Title\nbody', cursor=2)

    win._toggle_heading()

    assert headed(win, buf) == [[0, 5]]


def test_heading_covers_every_line_the_selection_touches():
    win, buf = make_window('one\ntwo\nthree')
    buf.select_range(buf.get_iter_at_offset(1), buf.get_iter_at_offset(9))

    win._toggle_heading()

    assert headed(win, buf) == [[0, 3], [4, 7], [8, 13]]


def test_heading_again_removes_it_when_every_line_has_it():
    win, buf = make_window('one\ntwo')
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())
    win._toggle_heading()

    win._toggle_heading()

    assert headed(win, buf) == []


def test_heading_makes_all_lines_headings_when_only_some_are():
    win, buf = make_window('one\ntwo')
    buf.apply_tag(win._heading_tag, buf.get_iter_at_offset(0),
                  buf.get_iter_at_offset(3))
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    win._toggle_heading()

    assert headed(win, buf) == [[0, 3], [4, 7]]


def test_heading_leaves_code_lines_and_dividers_alone():
    win, buf = make_window('Title\nls -l\n---', cursor=0)
    buf.apply_tag(win._code_tag, buf.get_iter_at_offset(6),
                  buf.get_iter_at_offset(11))
    win._divider_lines = [2]
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    win._toggle_heading()

    assert headed(win, buf) == [[0, 5]]


def test_heading_on_an_empty_line_waits_for_the_first_typed_text():
    win, buf = make_window('one\n\ntwo', cursor=4)

    win._toggle_heading()

    assert headed(win, buf) == []
    assert win._heading_active
    assert 'pinned' in win._format_btn.context.classes


def test_heading_on_an_empty_line_again_cancels_the_wait():
    win, buf = make_window('one\n\ntwo', cursor=4)
    win._toggle_heading()

    win._toggle_heading()

    assert not win._heading_active
    assert 'pinned' not in win._format_btn.context.classes


def test_the_first_text_typed_after_choosing_heading_becomes_the_heading():
    win, buf = make_window('one\n\ntwo', cursor=4)
    win._toggle_heading()

    type_text(win, buf, 'Plan')

    assert headed(win, buf) == [[4, 8]]
    assert win._heading_active
