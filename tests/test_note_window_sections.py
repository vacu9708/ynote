"""A section of a note folds and opens, keeps its end, and is left with Enter
or taken away with Backspace. ▾ and ▸ are its open and folded title marks and
¤ stands for its invisible end line in these tests."""
from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

from tests.test_note_window_heading import make_window as plain_window
from ynote.config import EXPAND_END


def sec(text):
    return text.replace('¤', EXPAND_END)


def shown(buf):
    return buf.get_slice(buf.get_start_iter(), buf.get_end_iter(),
                         True).replace(EXPAND_END, '¤')


def make_window(text, cursor=0):
    win, buf = plain_window(sec(text), cursor)
    win.tv.scroll_mark_onscreen = lambda mark: None
    for name in ('fold', 'expand_marker', 'expand_title', 'expand_end'):
        setattr(win, f'_{name}_tag', buf.create_tag(name))
    win._hl_tag = buf.create_tag('search-hl')
    win._expand_depth_tags = {}
    win._expand_unit = 20
    win._line_spacing = (1, 2)
    win._normalizing = False
    win._flush_snapshot = lambda: None
    win._refresh_line_styles = lambda: win._apply_sections(buf)
    win._queue_code_margins = lambda: None
    win._apply_sections(buf)
    return win, buf


def cursor(buf):
    return buf.get_iter_at_mark(buf.get_insert()).get_offset()


def press(win, keyval, state=0):
    return win._on_tv_key_press(
        win.tv, SimpleNamespace(state=state, keyval=keyval))


def test_ctrl_enter_on_the_title_folds_and_hides_the_content():
    win, buf = make_window('▾ Test\nrun it\n¤\nafter', cursor=3)

    assert press(win, Gdk.KEY_Return, Gdk.ModifierType.CONTROL_MASK)

    assert shown(buf) == '▸ Test\nrun it\n¤\nafter'
    assert win._hidden_lines == {1, 2}


def test_folding_moves_a_cursor_in_the_content_to_the_title():
    win, buf = make_window('▾ Test\nrun it\n¤\nafter', cursor=9)

    win._toggle_sections([0])

    assert cursor(buf) == 6


def test_an_open_section_hides_nothing_and_puts_its_content_in_its_box():
    win, buf = make_window('▾ Test\nrun it\n¤\nafter')

    assert win._hidden_lines == set()
    assert win._line_depth == {1: 1}
    assert win._expand_boxes == [(0, 2, 0)]


def test_backspace_after_an_expand_takes_an_empty_line_into_it():
    win, buf = make_window('▾ Test\nrun it\n¤\n\nafter', cursor=16)

    assert press(win, Gdk.KEY_BackSpace)

    assert shown(buf) == '▾ Test\nrun it\n¤\nafter'
    assert cursor(buf) == 13


def test_delete_never_joins_a_line_to_an_expands_end():
    win, buf = make_window('▾ Test\nrun it\n¤\nafter', cursor=13)

    assert press(win, Gdk.KEY_Delete)

    assert shown(buf) == '▾ Test\nrun it\n¤\nafter'


def test_enter_on_an_empty_last_line_goes_on_below_the_section():
    win, buf = make_window('▾ Test\nrun it\n\n¤\nafter', cursor=14)

    assert press(win, Gdk.KEY_Return)

    assert shown(buf) == '▾ Test\nrun it\n¤\n\nafter'
    assert cursor(buf) == 16


def test_backspace_at_the_title_start_keeps_the_content():
    win, buf = make_window('▾ Test\nrun it\n¤\nafter', cursor=2)

    assert press(win, Gdk.KEY_BackSpace)

    assert shown(buf) == 'Test\nrun it\nafter'


def test_insert_section_wraps_the_selected_lines():
    win, buf = make_window('one\ntwo\nthree')
    buf.select_range(buf.get_iter_at_offset(0), buf.get_iter_at_offset(7))

    win._insert_section()

    assert shown(buf) == '▾ \none\ntwo\n¤\nthree'
    assert cursor(buf) == 2


def test_insert_section_on_an_empty_last_line_leaves_a_line_after_it():
    win, buf = make_window('text\n', cursor=5)

    win._insert_section()

    assert shown(buf) == 'text\n▾ \n\n¤\n'


def test_an_end_left_alone_is_taken_out_and_a_section_never_ended_is_ended():
    win, buf = make_window('¤\n▾ Test\nbody')

    assert win._normalize_sections()

    assert shown(buf) == '▾ Test\nbody\n¤\n'


def test_a_search_match_shows_a_folded_expand_open_without_changing_it():
    win, buf = make_window('▸ Test\nrun it\n¤\nafter')
    assert win._hidden_lines == {1, 2}

    buf.apply_tag(win._hl_tag, buf.get_iter_at_offset(7),
                  buf.get_iter_at_offset(10))
    win._apply_sections(buf)

    assert win._hidden_lines == set()
    assert shown(buf) == '▸ Test\nrun it\n¤\nafter'

    buf.remove_tag(win._hl_tag, buf.get_start_iter(), buf.get_end_iter())
    win._apply_sections(buf)

    assert win._hidden_lines == {1, 2}
