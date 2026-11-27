"""Inline code has a figure space at each end of it for padding: the cursor
steps over it, Backspace and Delete skip it, and it is made and removed with
the code. · stands for such a space in the text of these tests."""
from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

from tests.test_note_window_heading import make_window, type_text
from ynote.config import CODE_PAD_CHAR, OLD_CODE_PAD_CHAR


def pd(text):
    return text.replace('·', CODE_PAD_CHAR)


def text_of(buf):
    return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)


def code(text, first, last, cursor=None):
    """A window with `text` whose offsets first..last are inline code."""
    win, buf = make_window(text, cursor=first if cursor is None else cursor)
    buf.apply_tag(win._backtick_tag, buf.get_iter_at_offset(first),
                  buf.get_iter_at_offset(last))
    # What follows the cursor, as in the window.
    buf.connect(
        'mark-set', lambda b, it, mark: win._sync_format_state()
        if mark is b.get_insert() else None)
    return win, buf


def ranges(win):
    return win._get_tag_ranges(win._backtick_tag)


def cursor(buf):
    return buf.get_iter_at_mark(buf.get_insert()).get_offset()


def at(buf, offset):
    buf.place_cursor(buf.get_iter_at_offset(offset))


def press(win, keyval):
    return win._on_tv_key_press(
        win.tv, SimpleNamespace(state=0, keyval=keyval))


# "x ␣ab␣ y": the code is offsets 2..6, so 2 is before its first space, 3 is
# inside it, 5 is inside at the end, and 6 is after its last space.
PADDED = pd('x ·ab· y')


def padded(cursor=2):
    win, buf = code(PADDED, 2, 6, cursor)
    win._sync_format_state()
    return win, buf


def test_the_spaces_at_the_ends_of_a_range_are_its_padding():
    win, buf = padded()

    assert [win._pad_kind(buf, o) for o in range(8)] == [
        None, None, 'lead', None, None, 'trail', None, None]


def test_a_range_of_one_space_or_with_a_space_inside_has_no_padding_to_find():
    win, buf = code('a b c', 0, 5)

    assert [win._pad_kind(buf, o) for o in range(5)] == [
        None, None, None, None, None]


def test_the_cursor_after_the_last_space_is_outside_the_code():
    win, buf = padded(cursor=6)
    assert not win._code_active

    at(buf, 5)
    win._sync_format_state()
    assert win._code_active

    at(buf, 3)
    win._sync_format_state()
    assert win._code_active

    at(buf, 2)
    win._sync_format_state()
    assert not win._code_active


def test_turning_code_on_before_it_steps_over_the_first_space():
    win, buf = padded(cursor=2)

    win._toggle_inline_code()

    assert cursor(buf) == 3
    assert win._code_active


def test_turning_code_off_at_the_end_of_it_steps_out_over_the_last_space():
    win, buf = padded(cursor=5)
    assert win._code_active

    win._toggle_inline_code()

    assert cursor(buf) == 6
    assert not win._code_active
    type_text(win, buf, 'z')
    assert ranges(win) == [[2, 6]]


def test_turning_code_on_after_it_steps_in_over_the_last_space():
    win, buf = padded(cursor=6)

    win._toggle_inline_code()
    type_text(win, buf, 'c')

    assert text_of(buf) == pd('x ·abc· y')
    assert ranges(win) == [[2, 7]]


def test_turning_code_off_in_the_middle_adds_no_text_until_one_is_typed():
    win, buf = code(pd('x ·abcd· y'), 2, 8, cursor=5)
    win._sync_format_state()
    assert win._code_active

    win._toggle_inline_code()

    assert text_of(buf) == pd('x ·abcd· y')
    assert cursor(buf) == 5
    assert not win._code_active
    type_text(win, buf, 'q')
    win._normalize_code_pads()
    assert text_of(buf) == pd('x ·ab·q·cd· y')
    assert ranges(win) == [[2, 6], [7, 11]]
    assert cursor(buf) == 7


def test_range_gets_its_spaces_from_normalizing():
    win, buf = code('run ls now', 4, 6, cursor=6)

    changed = win._normalize_code_pads()

    assert changed
    assert text_of(buf) == pd('run ·ls· now')
    assert ranges(win) == [[4, 8]]
    # The cursor was at the end of the code, and stays inside it.
    assert cursor(buf) == 7
    assert not win._normalize_code_pads()


def test_a_range_of_spaces_alone_is_taken_away():
    win, buf = code('a    b', 1, 5, cursor=3)

    win._normalize_code_pads()

    assert text_of(buf) == 'ab'
    assert ranges(win) == []
    assert cursor(buf) == 1


def test_every_range_of_a_line_is_normalized():
    win, buf = code('a b c d', 0, 1)
    buf.apply_tag(win._backtick_tag, buf.get_iter_at_offset(4),
                  buf.get_iter_at_offset(5))

    win._normalize_code_pads()

    assert text_of(buf) == pd('·a· b ·c· d')
    assert ranges(win) == [[0, 3], [6, 9]]


def test_backspace_after_the_last_space_deletes_the_character_before_it():
    win, buf = padded(cursor=6)

    assert press(win, Gdk.KEY_BackSpace)

    assert text_of(buf) == pd('x ·a· y')
    assert cursor(buf) == 5


def test_backspace_after_the_first_space_deletes_the_character_before_the_code():
    win, buf = padded(cursor=3)

    assert press(win, Gdk.KEY_BackSpace)

    assert text_of(buf) == pd('x·ab· y')
    assert cursor(buf) == 2


def test_delete_before_the_last_space_deletes_the_character_after_the_code():
    win, buf = padded(cursor=5)

    assert press(win, Gdk.KEY_Delete)

    assert text_of(buf) == pd('x ·ab·y')


def test_delete_before_the_first_space_deletes_the_first_character_of_the_code():
    win, buf = padded(cursor=2)

    assert press(win, Gdk.KEY_Delete)

    assert text_of(buf) == pd('x ·b· y')


def test_backspace_over_the_last_character_of_code_takes_both_spaces_too():
    win, buf = code(pd('x ·a· y'), 2, 5, cursor=5)
    assert press(win, Gdk.KEY_BackSpace)       # the 'a'
    assert text_of(buf) == pd('x ·· y')

    win._normalize_code_pads()

    assert text_of(buf) == 'x  y'
    assert ranges(win) == []


def test_turning_code_off_on_a_selection_takes_the_spaces_with_it():
    win, buf = padded()
    buf.select_range(buf.get_iter_at_offset(3), buf.get_iter_at_offset(5))

    win._toggle_inline_code()

    assert text_of(buf) == 'x ab y'
    assert ranges(win) == []


def test_turning_code_off_on_a_selection_with_the_spaces_in_it_takes_them_too():
    win, buf = padded()
    buf.select_range(buf.get_iter_at_offset(2), buf.get_iter_at_offset(6))

    win._toggle_inline_code()

    assert text_of(buf) == 'x ab y'
    assert ranges(win) == []


def test_turning_code_off_on_the_middle_of_a_selection_splits_it_with_spaces():
    win, buf = code(pd('x ·abc· y'), 2, 7)
    buf.select_range(buf.get_iter_at_offset(4), buf.get_iter_at_offset(5))

    win._toggle_inline_code()

    assert text_of(buf) == pd('x ·a·b·c· y')
    assert ranges(win) == [[2, 5], [6, 9]]


def test_turning_code_on_on_a_selection_gives_it_spaces():
    win, buf = make_window('run ls now')
    buf.select_range(buf.get_iter_at_offset(4), buf.get_iter_at_offset(6))

    win._toggle_inline_code()

    assert text_of(buf) == pd('run ·ls· now')
    assert ranges(win) == [[4, 8]]
    assert [i.get_offset() for i in buf.get_selection_bounds()] == [5, 7]


def test_backtick_wrapped_text_becomes_code_and_the_cursor_ends_after_it():
    win, buf = make_window('say `ls', cursor=7)

    type_text(win, buf, '`')

    assert text_of(buf) == pd('say ·ls·')
    assert ranges(win) == [[4, 8]]
    assert cursor(buf) == 8
    assert not win._code_active


def test_backticks_in_a_code_block_stay_backticks():
    win, buf = make_window('echo `date', cursor=10)
    buf.apply_tag(win._code_tag, buf.get_start_iter(), buf.get_end_iter())

    type_text(win, buf, '`')

    assert text_of(buf) == 'echo `date`'
    assert ranges(win) == []


def test_backticks_on_two_lines_do_not_make_code_together():
    win, buf = make_window('a `b\nc d', cursor=7)

    type_text(win, buf, '`')

    assert text_of(buf) == 'a `b\nc `d'
    assert ranges(win) == []


def test_plain_spaces_that_padded_code_in_an_older_note_become_pads():
    win, buf = code('x  ab  y', 2, 6, cursor=4)

    assert win._normalize_code_pads()

    assert text_of(buf) == pd('x ·ab· y')
    assert ranges(win) == [[2, 6]]
    assert cursor(buf) == 4
    assert not win._normalize_code_pads()


def test_en_spaces_that_padded_code_before_1_14_become_pads():
    old = OLD_CODE_PAD_CHAR
    win, buf = code(f'x {old}ab{old} y', 2, 6, cursor=4)

    assert win._normalize_code_pads()

    assert text_of(buf) == pd('x ·ab· y')
    assert ranges(win) == [[2, 6]]
    assert cursor(buf) == 4


def selection(buf):
    insert = buf.get_iter_at_mark(buf.get_insert()).get_offset()
    bound = buf.get_iter_at_mark(buf.get_selection_bound()).get_offset()
    return insert, bound


def select(buf, bound, insert):
    buf.select_range(buf.get_iter_at_offset(insert),
                     buf.get_iter_at_offset(bound))


# In PADDED, 'x ·ab· y', the code is 2..6: 2 is before its first space, 3
# before the a, 5 after the b, and 6 after its last space.

def test_selecting_right_into_code_skips_its_first_space():
    win, buf = padded()
    select(buf, 2, 3)                  # Shift+Right from before the code

    win._keep_pads_out_of_selection(previous=2)

    assert selection(buf) == (4, 3)    # the a


def test_selecting_left_out_of_code_skips_its_last_space():
    win, buf = padded()
    select(buf, 6, 5)                  # Shift+Left from after the code

    win._keep_pads_out_of_selection(previous=6)

    assert selection(buf) == (4, 5)    # the b


def test_selecting_back_over_a_space_gives_it_up_with_the_character():
    win, buf = padded()
    select(buf, 0, 3)                  # from 4 back to 3, after the space

    win._keep_pads_out_of_selection(previous=4)

    assert selection(buf) == (2, 0)


def test_a_selection_over_the_whole_code_keeps_its_spaces_inside():
    win, buf = padded()
    select(buf, 0, 8)

    win._keep_pads_out_of_selection(previous=7)

    assert selection(buf) == (8, 0)


def test_a_selection_moved_right_out_of_the_code_takes_the_character_after_it():
    win, buf = padded()
    select(buf, 3, 6)                  # Shift+Right over the last space

    win._keep_pads_out_of_selection(previous=5)

    assert selection(buf) == (7, 3)


def test_a_selection_dragged_over_the_space_stops_at_the_text():
    win, buf = padded()
    select(buf, 3, 6)                  # dragged right, over the last space

    win._keep_pads_out_of_selection(previous=5, keyboard=False)

    assert selection(buf) == (5, 3)


def test_a_selection_dragged_into_the_code_from_before_it_starts_at_the_text():
    win, buf = padded()
    select(buf, 0, 3)                  # dragged right, to after the space

    win._keep_pads_out_of_selection(previous=2, keyboard=False)

    assert selection(buf) == (2, 0)
