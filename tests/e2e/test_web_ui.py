"""T. The window of a 2.0 note: its bars, menus, and find. See BEHAVIORS.md."""
import pytest

from tests.e2e.driver import center, clipboard_text, extents, find_all, name, role, settle, showing, wait_until
from tests.e2e.web import (
    assert_saved, choose, menu, menu_button, menu_items, menu_open, saved_field, saved_note, start)

pytestmark = [pytest.mark.web]

EXPAND_CLOSED = '▸ '
EXPAND_END = '⁤'


def test_T1_a_toolbar_button_applies_its_format_to_the_selection(app, inp):
    note = start(app, 'hello world')
    inp.key('shift+home')
    note.press('Bold')
    assert_saved(app, "paragraph('hello world'[strong])")


def test_T2_a_menu_reaches_past_a_small_note_and_its_item_applies(app, inp):
    note = start(app, 'hello', w=240, h=240)
    note.press('More to insert')
    _mx, my, _mw, _mh = extents(menu(app))
    _nx, ny, _nw, _nh = note.box
    assert my < ny, 'the menu stays inside the note'
    choose(app, 'Divider')
    assert not menu_open(app)
    inp.type('below')
    assert_saved(app, "paragraph('hello') horizontal_rule() paragraph('below')")


def test_T3_a_click_outside_a_menu_closes_it_and_does_nothing_else(app, inp):
    note = start(app, 'hello')
    note.press('Note menu')
    menu(app)
    note.click_text(2, 10)          # on the text, before "hello"
    wait_until(lambda: not menu_open(app), what='the menu to close')
    inp.type('X')
    assert_saved(app, "paragraph('helloX')")


def test_T4_keys_move_in_a_menu_and_enter_chooses(app, inp):
    note = start(app, 'hello')
    note.press('More to insert')
    menu(app)
    inp.key('down')                 # Quote, the first
    inp.key('enter')
    wait_until(lambda: not menu_open(app), what='the menu to close')
    assert_saved(app, "blockquote(paragraph('hello')) paragraph()")


def test_T5_esc_closes_a_menu_and_nothing_changes(app, inp):
    note = start(app, 'hello')
    note.press('More to insert')
    menu(app)
    inp.key('down')
    inp.key('esc')
    wait_until(lambda: not menu_open(app), what='the menu to close')
    inp.type('!')
    assert_saved(app, "paragraph('hello!')")


def test_T6_a_color_from_the_note_menu_is_the_notes_and_saved(app, inp):
    note = start(app, 'hello')
    note.press('Note menu')
    inp.click(*center(menu_button(app, 'Blue')))
    saved_field(app, 'color', 'blue')


def test_T7_font_size_from_the_note_menu_is_saved(app, inp):
    note = start(app, 'hello')
    note.press('Note menu')
    inp.click(*center(menu_button(app, 'A+')))
    inp.click(*center(menu_button(app, 'A+')))
    saved_field(app, 'font_size', 16)


def test_T8_right_click_in_a_table_cell_adds_a_row(app, inp):
    rows = [[{'text': 'k'}, {'text': 'v'}], [{'text': 'a'}, {'text': 'b'}]]
    note = start(app, '￼', tables=[{'offset': 0, 'rows': rows}])
    note.click_text(14, 18, button=3)   # in "k", the first cell
    choose(app, 'Insert row below')
    assert_saved(app, "table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
                      "table_row(table_cell(paragraph()) table_cell(paragraph())) "
                      "table_row(table_cell(paragraph('a')) table_cell(paragraph('b')))) paragraph()")


def test_T9_copy_on_a_code_block_copies_the_whole_block(app, inp):
    note = start(app, 'ls -l\npwd', code_ranges=[[0, 9]])
    copy = note.find_button('Copy')
    inp.move(*center(copy))
    settle(0.3)
    inp.click(*center(copy))
    wait_until(lambda: clipboard_text() == 'ls -l\npwd', what='the block on the clipboard')


def test_T10_delete_asks_on_the_note_and_deletes_it(app, inp):
    note = start(app, 'hello')
    note.press('Note menu')
    choose(app, 'Delete note')
    note.press('Delete')
    wait_until(lambda: app.saved() == [], what='no saved notes')


def test_T11_f2_renames_the_note(app, inp):
    start(app, 'hello')
    inp.key('F2')
    inp.type('Renamed')
    inp.key('enter')
    saved_field(app, 'title', 'Renamed')
    app.note('Renamed')


def test_T12_find_moves_through_matches_and_esc_leaves_the_current_selected(app, inp):
    start(app, 'aa bb aa')
    inp.key('ctrl+f')
    inp.type('aa')
    inp.key('enter')                # the second "aa"
    inp.key('esc')
    inp.type('X')
    assert_saved(app, "paragraph('aa bb X')")


def test_T13_a_match_in_a_folded_expand_opens_it(app, inp):
    start(app, f'top\n{EXPAND_CLOSED}T\nsecret\n{EXPAND_END}')
    inp.key('ctrl+f')
    inp.type('secret')
    inp.key('esc')
    inp.type('X')
    assert_saved(app, "paragraph('top') expand(expand_title('T') paragraph('X')) paragraph()")
    assert saved_note(app)['doc']['content'][1]['attrs']['open'] is True


def tooltip(note, expected):
    """Wait for the tooltip to read expected; found again each time, as
    WebKit 2.50 (22.04) makes it anew when its text changes."""
    def read():
        for tip in find_all(note.frame, lambda a: role(a) == 'tool tip'):
            try:
                if showing(tip) and name(tip) == expected:
                    return True
            except Exception:
                pass
        return None
    wait_until(read, what=f'the tooltip {expected!r}')


def test_T15_a_tools_tooltip_shows_its_name_markdown_and_keys(app, inp):
    note = start(app, 'hello')
    inp.move(*center(note.button('Bold')))
    tooltip(note, 'Bold**text**CtrlB')
    inp.move(*center(note.button('More to insert')))
    tooltip(note, 'More to insert')


def test_T14_a_narrow_note_puts_the_toolbar_end_into_plus(app, inp):
    note = start(app, 'hello', w=230, h=240)
    shown = note.buttons()
    assert 'Bold' in shown and 'Table' not in shown
    note.press('More to insert')
    first = [i.get_name() for i in menu_items(app)]
    assert any(n.startswith('Table') for n in first[:4]), first


def test_T16_a_note_is_not_resized_smaller_than_it_can_be_used(app, inp):
    note = start(app, 'hello')
    x, y, w, h = note.box
    inp.drag((x + w - 3, y + h - 3), (x + 10, y + 10))
    settle(0.5)
    _x, _y, w, h = note.box
    assert w >= 180 and h >= 120, (w, h)


def test_T17_a_note_saved_too_small_opens_at_the_least_size(app, inp):
    note = start(app, 'hello', w=20, h=10)
    _x, _y, w, h = note.box
    assert w >= 180 and h >= 120, (w, h)


def hide(app, inp, title):
    note = app.note(title)
    from tests.e2e.web import WebNote
    WebNote(app, note.frame).press('Hide note')


def test_T18_hidden_notes_lists_them_latest_hidden_first_and_shows_one(app, inp):
    notes = [{'id': n, 'title': n, 'text': n, 'x': 60 + 360 * i, 'y': 80, 'w': 300, 'h': 300}
             for i, n in enumerate(['test', 'a', 'b'])]
    app.write_notes(notes)
    app.start()
    hide(app, inp, 'a')
    hide(app, inp, 'b')
    from tests.e2e.web import WebNote
    note = WebNote(app, app.note('test').frame)
    note.press('Note menu')
    choose(app, 'Hidden notes')
    names = [i.get_name() for i in menu_items(app)]
    assert names[0].startswith('b') and names[1].startswith('a'), names
    choose(app, 'a')
    app.note('a')
    wait_until(lambda: saved_note(app, 'a').get('hidden') is False, what='a shown')


def test_T19_show_all_shows_every_hidden_note(app, inp):
    notes = [{'id': n, 'title': n, 'text': n, 'x': 60 + 360 * i, 'y': 80, 'w': 300, 'h': 300}
             for i, n in enumerate(['test', 'a', 'b'])]
    app.write_notes(notes)
    app.start()
    hide(app, inp, 'a')
    hide(app, inp, 'b')
    from tests.e2e.web import WebNote
    WebNote(app, app.note('test').frame).press('Note menu')
    choose(app, 'Hidden notes')
    choose(app, 'Show all')
    app.note('a')
    app.note('b')


def test_T20_f1_shows_the_shortcuts_with_their_keys_and_the_version(app, inp):
    from tests.e2e.driver import Atspi
    from ynote import __version__
    start(app, 'hello')
    inp.key('F1')

    def page_text():
        for window in app.windows():
            if role(window) != 'window':
                continue
            texts = []
            for acc in find_all(window, lambda a: a.get_text_iface() is not None, limit=40):
                texts.append(Atspi.Text.get_text(acc, 0, Atspi.Text.get_character_count(acc)))
            text = ' '.join(texts)
            if 'Bold' in text:
                return text
        return None
    text = wait_until(page_text, what='the shortcuts')
    assert f'Ynote {__version__}' in text and 'Ctrl' in text, text[:400]


def test_T21_a_collapsed_note_is_its_title_bar(app, inp):
    note = start(app, 'hello')
    note.press('Collapse')
    wait_until(lambda: 30 <= note.box[3] <= 40, what='the note as tall as its title bar')
    note.press('Expand')
    wait_until(lambda: note.box[3] >= 300, what='the note back at its height')


def test_T22_a_click_outside_closes_the_shortcuts(app, inp):
    start(app, 'hello')
    inp.key('F1')
    settle(0.8)
    inp.click(1500, 900)              # the desktop, past every window
    settle(0.5)
    from tests.e2e.driver import Atspi

    def shortcuts_shown():
        for window in app.windows():
            if role(window) != 'window':
                continue
            for acc in find_all(window, lambda a: a.get_text_iface() is not None, limit=40):
                if 'Bold' in Atspi.Text.get_text(acc, 0, Atspi.Text.get_character_count(acc)):
                    return True
        return False
    wait_until(lambda: not shortcuts_shown(), what='the shortcuts to close')
    app.note('test')


def test_T23_the_note_menu_starts_with_new_note_and_hidden_notes_and_ends_with_delete(app, inp):
    note = start(app, 'hello')
    note.press('Note menu')
    names = [i.get_name() for i in menu_items(app)]
    assert names[0].startswith('New note') and names[1].startswith('Hidden notes'), names
    assert names[-1].startswith('Delete note'), names


def test_T24_a_wheel_notch_scrolls_as_far_as_in_1x(app, inp):
    note = start(app, '\n'.join(f'line {i}' for i in range(200)), h=700)
    from tests.e2e.web import text_holding
    from tests.e2e.driver import Atspi

    def top_of(needle):
        acc, at = text_holding(note, needle)
        return Atspi.Text.get_character_extents(acc, at, Atspi.CoordType.SCREEN).y
    before = top_of('line 30')
    x, y = note.text_point(80, 100)
    inp.scroll(x, y, down=True, notches=1)
    settle(0.05)
    at_once = before - top_of('line 30')
    settle(0.6)
    moved = before - top_of('line 30')
    # As far as GTK's step, the view's height to the 2/3 power, about 75px
    # here, and all of it at once, not animated.
    assert 65 <= moved <= 90, moved
    assert at_once == moved, (at_once, moved)
