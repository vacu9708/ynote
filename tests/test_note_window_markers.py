"""A bullet or a to-do box is not text: no format covers it, no code block takes
it in, and the cursor and a selection never end inside one. A selection takes
it whole or not at all."""
from types import SimpleNamespace

import gi
import pytest
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

from ynote.note_window import NoteWindow


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf

    def get_buffer(self):
        return self._buf


def make_window(text, cursor=0):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    win._code_tag = buf.create_tag('code')
    win._heading_tag = buf.create_tag('heading')
    win._bold_tag = buf.create_tag('bold')
    win._backtick_tag = buf.create_tag('backtick')
    win._divider_lines = []
    win._snap_sid = None
    win._pending_format_inserts = []
    win._take_snapshot = lambda: None
    win._queue_save = lambda: None
    win._sync_format_state = lambda: None
    win._refresh_format_buttons = lambda: None
    buf.place_cursor(buf.get_iter_at_offset(cursor))
    return win, buf


def tag_range(buf, tag, start, end):
    buf.apply_tag(tag, buf.get_iter_at_offset(start), buf.get_iter_at_offset(end))


def tagged(win, tag):
    return win._get_tag_ranges(tag)


def press(win, keyval):
    return win._on_tv_key_press(win.tv, SimpleNamespace(state=0, keyval=keyval))


def text_of(buf):
    return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)


def test_a_marker_ends_where_the_text_of_the_item_starts():
    win, buf = make_window('• one\n    ☐ two\nplain')

    assert win._marker_end(0) == 2
    assert win._marker_end(1) == 6 + 4 + 2
    assert win._marker_end(2) is None


def test_a_bullet_in_a_code_line_is_code_and_has_no_marker():
    win, buf = make_window('• in code\nplain')
    tag_range(buf, win._code_tag, 0, 9)

    assert win._marker_end(0) is None


def test_text_segments_leave_out_each_marker_its_indent_and_each_line_break():
    win, buf = make_window('• one\n  ☐ two\nplain')

    segments = win._text_segments(0, buf.get_char_count())

    assert segments == [(2, 5), (10, 13), (14, 19)]
    assert [text_of(buf)[s:e] for s, e in segments] == ['one', 'two', 'plain']


def test_bold_over_several_list_lines_does_not_cover_the_markers():
    win, buf = make_window('• one\n☐ two\nplain')
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    win._toggle_tag(win._bold_tag)

    covered = ''.join(text_of(buf)[s:e] for s, e in tagged(win, win._bold_tag))
    assert '•' not in covered and '☐' not in covered
    assert 'one' in covered and 'two' in covered and 'plain' in covered


def test_bold_toggles_off_again_when_all_the_text_but_the_markers_has_it():
    win, buf = make_window('• one\n☐ two')
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())
    win._toggle_tag(win._bold_tag)

    buf.select_range(buf.get_start_iter(), buf.get_end_iter())
    win._toggle_tag(win._bold_tag)

    assert tagged(win, win._bold_tag) == []


def test_a_list_item_does_not_become_a_heading_or_a_line_of_code():
    win, buf = make_window('• item\nplain', cursor=4)
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    assert win._heading_lines() == [1]
    win._toggle_code_block()

    assert tagged(win, win._code_tag) == [[7, 12]]


def test_bullets_and_checklists_skip_the_lines_of_a_code_block():
    win, buf = make_window('ls -l\nplain', cursor=0)
    tag_range(buf, win._code_tag, 0, 5)
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    win._toggle_bullet()

    assert text_of(buf) == 'ls -l\n• plain'


def test_a_format_over_several_lines_leaves_the_line_breaks_alone():
    # A line break with a format moved the indent of the next line.
    win, buf = make_window('first\n    • nested\nlast')
    buf.select_range(buf.get_iter_at_offset(2), buf.get_iter_at_offset(22))

    win._toggle_tag(win._backtick_tag)

    # 'rst', 'nested', and 'las': not the markers, nor the breaks after 'first'
    # (offset 5) and 'nested' (offset 18).
    covered = tagged(win, win._backtick_tag)
    assert [text_of(buf)[s:e] for s, e in covered] == ['rst', 'nested', 'las']
    assert all('\n' not in text_of(buf)[s:e] for s, e in covered)


def test_old_line_breaks_with_a_format_are_cleaned_when_a_note_opens():
    win, buf = make_window('first\n    • nested\nlast')
    # From 'rst' through the break at 5 into the indent, and a bold break at 18.
    tag_range(buf, win._backtick_tag, 2, 8)
    tag_range(buf, win._bold_tag, 18, 19)

    win._strip_marker_formats()

    assert tagged(win, win._backtick_tag) == [[2, 5]]
    assert tagged(win, win._bold_tag) == []


def test_old_formats_on_a_marker_are_taken_off():
    win, buf = make_window('• one\n☐ two')
    tag_range(buf, win._bold_tag, 0, 5)
    tag_range(buf, win._heading_tag, 6, 11)
    tag_range(buf, win._backtick_tag, 0, 2)

    win._strip_marker_formats()

    assert tagged(win, win._bold_tag) == [[2, 5]]
    assert tagged(win, win._heading_tag) == [[8, 11]]
    assert tagged(win, win._backtick_tag) == []


def test_backspace_at_the_start_of_an_item_removes_the_whole_marker():
    win, buf = make_window('• one\nplain', cursor=2)

    assert press(win, Gdk.KEY_BackSpace)

    assert text_of(buf) == 'one\nplain'


def test_backspace_inside_the_text_of_an_item_is_left_to_gtk():
    win, buf = make_window('• one', cursor=4)

    assert not press(win, Gdk.KEY_BackSpace)
    assert text_of(buf) == '• one'


def test_delete_at_the_end_of_a_line_takes_the_marker_of_the_next_item_first():
    win, buf = make_window('before\n• item', cursor=6)

    assert not press(win, Gdk.KEY_Delete)

    assert text_of(buf) == 'before\nitem'


def test_leaving_a_marker_goes_to_its_end_or_to_the_line_before():
    win, buf = make_window('first\n• item', cursor=8)
    mark = buf.get_insert()

    # Home, or a click on the marker, put the cursor inside it.
    buf.place_cursor(buf.get_iter_at_offset(6))
    win._leave_marker('insert', 12)
    assert buf.get_iter_at_mark(mark).get_offset() == 8

    # Left from the start of the item goes to the end of the line before.
    buf.place_cursor(buf.get_iter_at_offset(7))
    win._leave_marker('insert', 8, keyboard=True)
    assert buf.get_iter_at_mark(mark).get_offset() == 5
    assert not buf.get_has_selection()


def test_home_at_the_start_of_an_item_stays_there():
    win, buf = make_window('first\n• item', cursor=8)
    buf.place_cursor(buf.get_iter_at_offset(6))

    win._leave_marker('insert', 8, keyboard=True)

    assert buf.get_iter_at_mark(buf.get_insert()).get_offset() == 8


def test_a_click_on_the_marker_of_the_item_in_use_stays_on_its_line():
    win, buf = make_window('first\n• item', cursor=8)
    buf.place_cursor(buf.get_iter_at_offset(7))

    win._leave_marker('insert', 8)

    assert buf.get_iter_at_mark(buf.get_insert()).get_offset() == 8


def test_a_mouse_selection_takes_the_marker_it_reaches_over():
    win, buf = make_window('first\n• item', cursor=0)
    # A drag that started on the marker and went right.
    buf.select_range(buf.get_iter_at_offset(11), buf.get_iter_at_offset(7))

    win._leave_marker('selection_bound', None)

    start, end = buf.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (6, 11)


def test_a_mouse_selection_from_above_takes_the_marker_too():
    win, buf = make_window('first\n☐ item', cursor=0)
    buf.select_range(buf.get_iter_at_offset(7), buf.get_iter_at_offset(2))

    win._leave_marker('insert', 2)

    start, end = buf.get_selection_bounds()
    assert (start.get_offset(), end.get_offset()) == (2, 8)


def shift_arrow(win, buf, to, previous):
    """What GTK does for Shift+arrow: the cursor end moves, the other stays.
    Then what the mark-set handler does once GTK is done."""
    buf.move_mark(buf.get_insert(), buf.get_iter_at_offset(to))
    win._leave_marker('insert', previous, keyboard=True)
    return tuple(i.get_offset() for i in buf.get_selection_bounds())


@pytest.mark.parametrize('marker', ['• ', '☐ ', '☑ '])
def test_selecting_left_from_an_item_takes_the_marker_then_the_line_break(marker):
    win, buf = make_window('one\n' + marker + 'two', cursor=6)

    assert shift_arrow(win, buf, 5, 6) == (4, 6)
    # Past the start of the line, GTK reaches the line before by itself.
    assert shift_arrow(win, buf, 3, 4) == (3, 6)


def test_selecting_right_toward_an_item_takes_the_line_break_then_the_marker():
    win, buf = make_window('one\n• two', cursor=3)

    assert shift_arrow(win, buf, 4, 3) == (3, 4)
    assert shift_arrow(win, buf, 5, 4) == (3, 6)


def test_selecting_back_over_the_marker_gives_it_up_whole():
    win, buf = make_window('one\n• two', cursor=6)
    shift_arrow(win, buf, 5, 6)

    assert shift_arrow(win, buf, 5, 4) == ()
    assert buf.get_iter_at_mark(buf.get_insert()).get_offset() == 6


def test_shift_home_selects_the_text_and_a_second_one_the_marker():
    win, buf = make_window('one\n• two', cursor=9)

    assert shift_arrow(win, buf, 4, 9) == (6, 9)
    assert shift_arrow(win, buf, 4, 6) == (4, 9)


def test_moving_left_from_the_start_of_an_item_goes_to_the_line_before():
    win, buf = make_window('one\n• two', cursor=6)
    buf.place_cursor(buf.get_iter_at_offset(5))

    win._leave_marker('insert', 6, keyboard=True)

    assert buf.get_iter_at_mark(buf.get_insert()).get_offset() == 3
    assert buf.get_selection_bounds() == ()


def test_selecting_left_over_text_from_an_item_takes_the_marker_next():
    win, buf = make_window('one\n• two', cursor=8)
    buf.move_mark(buf.get_insert(), buf.get_iter_at_offset(6))

    assert shift_arrow(win, buf, 5, 6) == (4, 8)


@pytest.mark.parametrize('marker', ['• ', '☐ ', '☑ '])
def test_backspace_at_the_start_of_a_nested_item_outdents_it_one_level(marker):
    win, buf = make_window('\t\t' + marker + 'one', cursor=4)

    assert press(win, Gdk.KEY_BackSpace)
    assert text_of(buf) == '\t' + marker + 'one'
    assert buf.get_iter_at_mark(buf.get_insert()).get_offset() == 3

    assert press(win, Gdk.KEY_BackSpace)
    assert text_of(buf) == marker + 'one'

    # At the top level it takes off the marker, as before.
    assert press(win, Gdk.KEY_BackSpace)
    assert text_of(buf) == 'one'


def test_backspace_on_an_empty_nested_item_outdents_it_one_level():
    win, buf = make_window('• a\n\t• ', cursor=8)

    assert press(win, Gdk.KEY_BackSpace)

    assert text_of(buf) == '• a\n• '


def test_backspace_on_an_item_indented_by_spaces_takes_off_one_level():
    win, buf = make_window('      • one', cursor=8)

    assert press(win, Gdk.KEY_BackSpace)

    assert text_of(buf) == '  • one'


def test_tab_and_shift_tab_indent_an_item_by_one_tab():
    win, buf = make_window('• one', cursor=2)

    assert press(win, Gdk.KEY_Tab)
    assert press(win, Gdk.KEY_Tab)
    assert text_of(buf) == '\t\t• one'

    assert win._on_tv_key_press(win.tv, SimpleNamespace(
        state=Gdk.ModifierType.SHIFT_MASK, keyval=Gdk.KEY_ISO_Left_Tab))
    assert text_of(buf) == '\t• one'


def test_items_indented_by_spaces_get_tabs_and_keep_their_formats():
    win, buf = make_window('        • bold\n    plain\n      ☐ x')
    tag_range(buf, win._bold_tag, 10, 14)

    assert win._tab_list_indents()

    # Only list items: a plain line keeps its spaces.
    assert text_of(buf) == '\t\t• bold\n    plain\n\t  ☐ x'
    assert tagged(win, win._bold_tag) == [[4, 8]]
    assert not win._tab_list_indents()


def test_a_list_typed_after_spaces_is_indented_by_tabs():
    win, buf = make_window('    -', cursor=5)

    assert press(win, Gdk.KEY_space)

    assert text_of(buf) == '\t• '


def shift_tab(win):
    return win._on_tv_key_press(win.tv, SimpleNamespace(
        state=Gdk.ModifierType.SHIFT_MASK, keyval=Gdk.KEY_ISO_Left_Tab))


def test_tab_and_shift_tab_over_a_selection_indent_each_selected_item():
    win, buf = make_window('• one\nplain\n\t☐ two\n☑ three\n• after')
    # From inside "one" to inside "three": the last item is not selected.
    buf.select_range(buf.get_iter_at_offset(3), buf.get_iter_at_offset(23))

    assert press(win, Gdk.KEY_Tab)
    # A plain line keeps its text, and the selection stays.
    assert text_of(buf) == '\t• one\nplain\n\t\t☐ two\n\t☑ three\n• after'
    assert buf.get_has_selection()

    assert shift_tab(win)
    assert shift_tab(win)
    assert text_of(buf) == '• one\nplain\n☐ two\n☑ three\n• after'


def test_a_selection_ending_at_the_start_of_a_line_leaves_that_line():
    win, buf = make_window('• one\n• two')
    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(6))

    assert press(win, Gdk.KEY_Tab)

    assert text_of(buf) == '\t• one\n• two'


def test_tab_over_a_selection_without_list_items_is_left_to_gtk():
    win, buf = make_window('one\ntwo')
    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(5))

    assert not press(win, Gdk.KEY_Tab)
    assert not shift_tab(win)
    assert text_of(buf) == 'one\ntwo'
