"""Markdown typed into a note becomes its format, as the Format and Insert
menus show next to each item: "# " a heading, **text** bold, and ``` alone on
a line a code block. Each change is its own undo step."""
from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk

from tests.test_note_window_heading import make_window as plain_window
from ynote.config import CODE_ANCHOR, QUOTE_MARKER


def make_window(text, cursor=0):
    """A window whose buffer runs the typing handlers, connected once as
    in the window: a second copy would see the text the first one changed."""
    win, buf = plain_window(text, cursor)
    buf.connect('insert-text', win._on_buf_insert_text)
    buf.connect_after('insert-text', win._after_buf_insert_text)
    return win, buf


def text_of(buf):
    return buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)


def type_keys(win, buf, text):
    """Type text a key at a time: Space goes through the key handler first,
    as it does in the window."""
    for char in text:
        if char == ' ' and win._on_tv_key_press(
                win.tv, SimpleNamespace(state=0, keyval=Gdk.KEY_space)):
            continue
        buf.insert_at_cursor(char)


def test_hash_and_space_on_an_empty_line_makes_the_next_text_a_heading():
    win, buf = make_window('one\n', cursor=4)

    type_keys(win, buf, '# Plan')

    assert text_of(buf) == 'one\nPlan'
    assert win._get_tag_ranges(win._heading_tag) == [[4, 8]]


def test_hash_and_space_before_text_makes_its_line_a_heading():
    win, buf = make_window('#Plan', cursor=1)

    type_keys(win, buf, ' ')

    assert text_of(buf) == 'Plan'
    assert win._get_tag_ranges(win._heading_tag) == [[0, 4]]


def test_a_hash_after_other_text_stays_a_hash():
    win, buf = make_window('issue', cursor=5)

    type_keys(win, buf, ' # 4')

    assert text_of(buf) == 'issue # 4'
    assert win._get_tag_ranges(win._heading_tag) == []


def test_closing_double_asterisks_make_the_text_bold():
    win, buf = make_window('', cursor=0)

    type_keys(win, buf, 'a **big** deal')

    assert text_of(buf) == 'a big deal'
    assert win._get_tag_ranges(win._bold_tag) == [[2, 5]]


def test_asterisks_around_spaces_or_in_a_glob_stay_as_they_are():
    win, buf = make_window('', cursor=0)

    type_keys(win, buf, 'a ** b ** and src/**/*.py**')

    assert text_of(buf) == 'a ** b ** and src/**/*.py**'
    assert win._get_tag_ranges(win._bold_tag) == []


def test_three_backticks_alone_on_a_line_start_a_code_block():
    win, buf = make_window('run:\n', cursor=5)

    type_keys(win, buf, '```')

    assert text_of(buf) == 'run:\n' + CODE_ANCHOR
    assert win._is_code_line(buf, 1)


def test_three_backticks_after_text_are_not_a_code_block():
    win, buf = make_window('see ', cursor=4)

    type_keys(win, buf, '```')

    assert not win._is_code_line(buf, 0)


def test_the_insert_menu_lists_elements_with_their_markdown():
    win, buf = make_window('text')

    items = {item.label: (item.hint, item.keys)
             for item in win._insert_items()}

    assert items['Code block'] == ('```', 'Ctrl+Shift+C')
    assert items['Bullet list'] == ('- item', 'Ctrl+8')
    assert set(items) == {'Bullet list', 'Checklist', 'Quote', 'Code block',
                          'Divider', 'Expand', 'Table', 'Image…'}


def test_every_menu_item_has_an_icon():
    win, buf = make_window('text')

    for item in win._format_items() + win._insert_items():
        assert item.icon.strip()


def test_greater_than_and_space_start_a_quote():
    win, buf = make_window('', cursor=0)

    type_keys(win, buf, '> wise words')

    assert text_of(buf) == QUOTE_MARKER + 'wise words'


def test_enter_continues_a_quote_and_ends_it_on_an_empty_line():
    win, buf = make_window(QUOTE_MARKER + 'one', cursor=5)

    win._on_tv_key_press(win.tv, SimpleNamespace(state=0,
                                                 keyval=Gdk.KEY_Return))
    assert text_of(buf) == f'{QUOTE_MARKER}one\n{QUOTE_MARKER}'

    win._on_tv_key_press(win.tv, SimpleNamespace(state=0,
                                                 keyval=Gdk.KEY_Return))
    assert text_of(buf) == f'{QUOTE_MARKER}one\n'


def test_a_key_the_note_handles_itself_keeps_the_cursor_in_view():
    win, buf = make_window(QUOTE_MARKER + 'one', cursor=5)
    scrolled = []
    win.tv.scroll_mark_onscreen = scrolled.append

    win._on_tv_key_press(win.tv, SimpleNamespace(state=0,
                                                 keyval=Gdk.KEY_Return))

    assert scrolled == [buf.get_insert()]


def test_a_key_left_to_gtk_is_scrolled_by_gtk_alone():
    win, buf = make_window('plain', cursor=5)
    scrolled = []
    win.tv.scroll_mark_onscreen = scrolled.append

    handled = win._on_tv_key_press(win.tv, SimpleNamespace(
        state=0, keyval=Gdk.KEY_Return))

    assert not handled and scrolled == []
