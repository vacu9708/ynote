"""Bold, inline code, and heading follow the cursor, light up the Format
button and are checked in its menu, apply to typed text, and turn off on
Enter."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from tests.test_note_window_heading import make_window, type_text
from tests.test_note_window_code_pads import pd


def tag_range(buf, tag, start, end):
    buf.apply_tag(tag, buf.get_iter_at_offset(start),
                  buf.get_iter_at_offset(end))


def ranges(win, tag):
    return win._get_tag_ranges(tag)


def pinned(button):
    return 'pinned' in button.context.classes


def format_item(win, label):
    """(on, can be chosen) of an item of the Format menu."""
    for item in win._format_items():
        if item.label == label:
            return item.active, item.sensitive
    raise KeyError(label)


def test_the_cursor_after_bold_text_turns_bold_on():
    win, buf = make_window('plain bold')
    tag_range(buf, win._bold_tag, 6, 10)

    buf.place_cursor(buf.get_iter_at_offset(10))
    win._sync_format_state()

    assert win._bold_active and pinned(win._format_btn)
    assert format_item(win, 'Bold') == (True, True)
    assert not win._code_active
    assert format_item(win, 'Inline code') == (False, True)


def test_the_cursor_after_plain_text_turns_bold_off():
    win, buf = make_window('bold plain')
    tag_range(buf, win._bold_tag, 0, 4)

    buf.place_cursor(buf.get_iter_at_offset(10))
    win._sync_format_state()

    assert not win._bold_active and not pinned(win._format_btn)


def test_at_the_start_of_a_line_the_character_after_the_cursor_counts():
    win, buf = make_window('one\ncode')
    tag_range(buf, win._backtick_tag, 4, 8)

    buf.place_cursor(buf.get_iter_at_offset(4))
    win._sync_format_state()

    assert win._code_active and pinned(win._format_btn)


def test_at_the_start_of_a_list_item_or_quote_the_text_after_it_counts():
    for marker in ('• ', '☐ ', '▍ '):
        win, buf = make_window(f'one\n{marker}bold item')
        start = 4 + len(marker)
        tag_range(buf, win._bold_tag, start, start + 4)

        buf.place_cursor(buf.get_iter_at_offset(start))
        win._sync_format_state()

        assert win._bold_active, marker


def test_a_selection_counts_only_when_all_of_it_has_the_format():
    win, buf = make_window('bold plain')
    tag_range(buf, win._bold_tag, 0, 4)

    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(4))
    win._sync_format_state()
    assert win._bold_active

    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(6))
    win._sync_format_state()
    assert not win._bold_active


def test_the_cursor_on_a_heading_line_turns_heading_on():
    win, buf = make_window('Title\nbody')
    tag_range(buf, win._heading_tag, 0, 5)

    buf.place_cursor(buf.get_iter_at_offset(2))
    win._sync_format_state()
    assert win._heading_active and pinned(win._format_btn)

    buf.place_cursor(buf.get_iter_at_offset(8))
    win._sync_format_state()
    assert not win._heading_active and not pinned(win._format_btn)


def test_inline_code_turned_on_applies_to_typed_text():
    win, buf = make_window('Use ', cursor=4)
    win._toggle_inline_code()

    type_text(win, buf, 'ls')

    assert ranges(win, win._backtick_tag) == [[4, 6]]
    assert win._code_active


def test_typing_after_inline_code_continues_it():
    win, buf = make_window('Use ls', cursor=6)
    tag_range(buf, win._backtick_tag, 4, 6)
    win._sync_format_state()

    type_text(win, buf, ' -l')

    assert ranges(win, win._backtick_tag) == [[4, 9]]


def test_turning_inline_code_off_after_it_types_plain_text():
    win, buf = make_window('Use ls', cursor=6)
    tag_range(buf, win._backtick_tag, 4, 6)
    win._sync_format_state()

    win._toggle_inline_code()
    type_text(win, buf, ' now')

    assert ranges(win, win._backtick_tag) == [[4, 6]]
    assert not win._code_active and not pinned(win._format_btn)


def test_inline_code_turned_off_in_its_middle_splits_it_and_types_plain_text():
    win, buf = make_window(pd('run ·foobar· now'), cursor=8)
    tag_range(buf, win._backtick_tag, 4, 12)
    win._sync_format_state()
    assert win._code_active

    win._toggle_inline_code()
    # Nothing is in the text until something is typed.
    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True) \
        == pd('run ·foobar· now')
    type_text(win, buf, 'X')
    win._normalize_code_pads()

    # The letter has a space on each side, the end of one range and the start
    # of the next.
    assert buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True) \
        == pd('run ·foo·X·bar· now')
    assert ranges(win, win._backtick_tag) == [[4, 9], [10, 15]]
    assert not win._code_active


def test_bold_turned_off_in_its_middle_types_plain_text():
    win, buf = make_window('some words', cursor=7)
    tag_range(buf, win._bold_tag, 0, 10)
    win._sync_format_state()

    win._toggle_bold()
    type_text(win, buf, 'X')

    assert ranges(win, win._bold_tag) == [[0, 7], [8, 11]]


def test_typing_in_the_middle_of_inline_code_keeps_it_by_default():
    win, buf = make_window('run foobar now', cursor=7)
    tag_range(buf, win._backtick_tag, 4, 10)
    win._sync_format_state()

    type_text(win, buf, 'X')

    assert ranges(win, win._backtick_tag) == [[4, 11]]


def test_a_line_break_typed_in_inline_code_does_not_take_it():
    win, buf = make_window('run foobar now', cursor=7)
    tag_range(buf, win._backtick_tag, 4, 10)
    tag_range(buf, win._bold_tag, 4, 10)
    win._sync_format_state()

    type_text(win, buf, '\n')

    for tag in (win._backtick_tag, win._bold_tag):
        assert ranges(win, tag) == [[4, 7], [8, 11]]


def test_enter_turns_every_format_off():
    win, buf = make_window('words', cursor=5)
    tag_range(buf, win._bold_tag, 0, 5)
    tag_range(buf, win._backtick_tag, 0, 5)
    win._sync_format_state()
    assert win._bold_active and win._code_active

    type_text(win, buf, '\n')
    assert not (win._bold_active or win._code_active)
    assert not pinned(win._format_btn)

    type_text(win, buf, 'next')
    for tag in (win._bold_tag, win._backtick_tag):
        assert ranges(win, tag) == [[0, 5]]


def test_enter_at_the_end_of_a_heading_starts_a_plain_line():
    win, buf = make_window('Title', cursor=5)
    tag_range(buf, win._heading_tag, 0, 5)
    win._sync_format_state()
    assert win._heading_active

    type_text(win, buf, '\nbody')

    assert not win._heading_active and not pinned(win._format_btn)
    assert ranges(win, win._heading_tag) == [[0, 5]]


def test_bold_with_a_selection_toggles_the_text_and_follows_it():
    win, buf = make_window('one two')
    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(3))

    win._toggle_bold()
    assert ranges(win, win._bold_tag) == [[0, 3]]
    assert win._bold_active

    win._toggle_bold()
    assert ranges(win, win._bold_tag) == []
    assert not win._bold_active


def test_bold_is_off_in_a_heading_and_turns_on_and_off():
    win, buf = make_window('Title\nbody')
    tag_range(buf, win._heading_tag, 0, 5)

    buf.place_cursor(buf.get_iter_at_offset(5))
    win._sync_format_state()
    assert win._heading_active and not win._bold_active
    assert format_item(win, 'Bold') == (False, True)

    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(5))
    win._toggle_bold()
    assert ranges(win, win._bold_tag) == [[0, 5]]
    assert ranges(win, win._heading_tag) == [[0, 5]]

    win._toggle_bold()
    assert ranges(win, win._bold_tag) == []


def test_text_typed_in_a_heading_is_bold_once_bold_is_on():
    win, buf = make_window('', cursor=0)
    win._toggle_heading()
    assert not win._bold_active

    type_text(win, buf, 'Plan')
    win._toggle_bold()
    type_text(win, buf, ' B')

    assert ranges(win, win._heading_tag) == [[0, 6]]
    assert ranges(win, win._bold_tag) == [[4, 6]]


def test_bold_stays_when_a_line_becomes_a_heading_and_back():
    win, buf = make_window('Title', cursor=2)
    tag_range(buf, win._bold_tag, 0, 2)

    win._toggle_heading()
    assert ranges(win, win._heading_tag) == [[0, 5]]
    assert ranges(win, win._bold_tag) == [[0, 2]]

    win._toggle_heading()
    assert ranges(win, win._heading_tag) == []
    assert ranges(win, win._bold_tag) == [[0, 2]]
