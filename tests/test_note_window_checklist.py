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


def make_window(text, cursor=None):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    win._code_tag = buf.create_tag('code')
    win._heading_tag = buf.create_tag('heading')
    win._snap_sid = None
    win._history = [{'text': text, 'bold': [], 'code': [], 'backtick': [],
                     'images': []}]
    win._hist_pos = 0
    win._take_snapshot = lambda: None
    win._queue_save = lambda: None
    buf.place_cursor(buf.get_iter_at_offset(len(text) if cursor is None else cursor))
    return win, buf


def text_of(buf):
    return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)


def cursor_of(buf):
    return buf.get_iter_at_mark(buf.get_insert()).get_offset()


def press(win, keyval, state=0):
    return win._on_tv_key_press(win.tv, SimpleNamespace(state=state, keyval=keyval))


def type_space(text):
    win, buf = make_window(text)
    handled = press(win, Gdk.KEY_space)
    if not handled:
        buf.insert_at_cursor(' ')
    return text_of(buf), cursor_of(buf)


def test_typed_brackets_become_a_checkbox():
    assert type_space('[ ]') == ('☐ ', 2)
    assert type_space('[]') == ('☐ ', 2)
    assert type_space('  [x]') == ('  ☑ ', 4)


def test_markdown_task_after_a_bullet_becomes_a_checkbox():
    # "- " has already turned into a bullet by the time "[ ]" is typed.
    assert type_space('• [ ]') == ('☐ ', 2)


def test_dash_still_starts_a_bullet_and_other_text_is_left_alone():
    assert type_space('-') == ('• ', 2)
    assert type_space('a [ ]') == ('a [ ] ', 6)


def test_typed_checkbox_is_not_converted_in_a_code_block():
    win, buf = make_window('[ ]')
    buf.apply_tag(win._code_tag, buf.get_start_iter(), buf.get_end_iter())

    assert not press(win, Gdk.KEY_space)


def test_enter_continues_a_checklist_unchecked():
    win, buf = make_window('☑ done')
    press(win, Gdk.KEY_Return)

    assert text_of(buf) == '☑ done\n☐ '
    assert cursor_of(buf) == len('☑ done\n☐ ')


def test_enter_on_an_empty_checkbox_ends_the_list():
    win, buf = make_window('☐ a\n☐ ')
    press(win, Gdk.KEY_Return)

    assert text_of(buf) == '☐ a\n'


def test_tab_indents_a_checkbox_line():
    win, buf = make_window('☐ a')
    press(win, Gdk.KEY_Tab)

    assert text_of(buf) == '\t☐ a'


def test_ctrl_enter_toggles_the_selected_checkboxes_only():
    win, buf = make_window('☐ a\nplain\n☑ b\n• c')
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    assert press(win, Gdk.KEY_Return, Gdk.ModifierType.CONTROL_MASK) is True
    assert text_of(buf) == '☑ a\nplain\n☐ b\n• c'


def test_checklist_toggle_adds_replaces_and_removes_markers():
    win, buf = make_window('a\n• b\n    c')
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    win._toggle_checklist()
    assert text_of(buf) == '☐ a\n☐ b\n    ☐ c'

    buf.select_range(buf.get_start_iter(), buf.get_end_iter())
    win._toggle_checklist()
    assert text_of(buf) == 'a\nb\n    c'


def test_bullet_toggle_turns_a_checkbox_into_a_bullet():
    win, buf = make_window('☑ a', cursor=0)

    win._toggle_bullet()

    assert text_of(buf) == '• a'


def test_checkbox_bounds_cover_the_box_and_its_space():
    win, buf = make_window('  ☐ a ☐\nplain ☐')

    box, after = win._checkbox_bounds(0)
    assert (box.get_offset(), after.get_offset()) == (2, 4)
    assert win._checkbox_bounds(1) is None
