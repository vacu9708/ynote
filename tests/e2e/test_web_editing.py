"""U. Editing in a 2.0 note: code, headings, table headers, the / menu,
Enter in expands and code, pasting images, and finding in all notes. See
BEHAVIORS.md."""
import datetime
import os

import pytest

from gi.repository import GdkPixbuf

from tests.e2e.driver import Gdk, Gtk, pump, settle, wait_until
from tests.e2e.web import (
    WebNote, assert_saved, attrs_at, choose, ink, menu, menu_items, menu_open, saved_note, start, weights)

pytestmark = [pytest.mark.web]

EXPAND_OPEN = '▾ '
EXPAND_END = '⁤'


def test_U1_double_click_in_a_code_block_selects_its_line(app, inp):
    note = start(app, 'ls -l\npwd', code_ranges=[[0, 9]])
    x, y = note.text_point(26, 30)       # on "pwd", the second line
    inp.click(x, y, count=2)
    inp.type('X')
    assert_saved(app, "code_block('ls -l\\nX') paragraph()")


def test_U2_triple_click_in_a_code_block_selects_the_whole_block(app, inp):
    note = start(app, 'ls -l\npwd', code_ranges=[[0, 9]])
    x, y = note.text_point(26, 30)
    inp.click(x, y, count=3)
    inp.type('X')
    assert_saved(app, "code_block('X') paragraph()")


def test_U3_bold_in_a_heading_is_drawn_bolder(app, inp):
    # The same letters, plain and bold, in a heading. WebKit tells any weight
    # from bold up as 700, so the pixels tell them apart.
    note = start(app, 'Lollol Lollol', heading_ranges=[[0, 13]], bold_ranges=[[7, 13]])
    assert int(attrs_at(note, 'Lollol').get('weight', 400)) >= 700
    acc_plain = ink(note, 'Lollol ')
    acc_bold = ink(note, ' Lollol')
    assert acc_bold > acc_plain * 1.08, (acc_plain, acc_bold)


def test_U4_bold_turns_off_in_a_table_header(app, inp):
    rows = [[{'text': 'Name', 'bold': [[0, 4]]}], [{'text': 'a'}]]
    note = start(app, '￼', tables=[{'offset': 0, 'rows': rows}])
    assert weights(note, 'Name')[0] >= 700
    note.click_text(14, 10)
    inp.key('home')
    inp.key('shift+end')
    inp.key('ctrl+b')
    assert_saved(app, "table(table_row(table_header(paragraph('Name'))) "
                      "table_row(table_cell(paragraph('a')))) paragraph()")
    assert weights(note, 'Name')[0] < 700


def test_U5_typing_in_a_new_tables_header_starts_bold(app, inp):
    note = start(app, '')
    note.press('Table')
    inp.type('Key')
    inp.key('tab')
    inp.key('tab')
    inp.key('tab')
    inp.type('v')
    assert_saved(app, "table(table_row(table_header(paragraph('Key'[strong])) table_header(paragraph()) "
                      "table_header(paragraph())) table_row(table_cell(paragraph('v')) table_cell(paragraph()) "
                      "table_cell(paragraph())) table_row(table_cell(paragraph()) table_cell(paragraph()) "
                      "table_cell(paragraph()))) paragraph()")


def test_U6_deleting_the_header_row_makes_the_next_row_the_header(app, inp):
    rows = [[{'text': 'k'}], [{'text': 'a'}], [{'text': 'b'}]]
    note = start(app, '￼', tables=[{'offset': 0, 'rows': rows}])
    note.click_text(14, 10, button=3)
    choose(app, 'Delete row')
    assert_saved(app, "table(table_row(table_header(paragraph('a'))) "
                      "table_row(table_cell(paragraph('b')))) paragraph()")


def test_U7_slash_expand_inserts_an_expand(app, inp):
    start(app, '')
    inp.type('/expand')
    menu(app)
    inp.key('enter')
    inp.type('T')
    assert_saved(app, "expand(expand_title('T') paragraph()) paragraph()")


def test_U8_slash_narrows_as_typed_and_inserts_the_date(app, inp):
    start(app, 'log ')
    inp.type('/da')
    names = [i.get_name() for i in menu_items(app)]
    assert names[0].startswith('Date'), names
    inp.key('enter')
    today = datetime.date.today().isoformat()
    assert_saved(app, f"paragraph('log {today}')")


def test_U9_a_path_typed_after_a_slash_stays_as_typed(app, inp):
    start(app, 'tail ')
    inp.type('/var/log/syslog ok')
    assert not menu_open(app)
    assert_saved(app, "paragraph('tail /var/log/syslog ok')")


def test_U10_esc_closes_the_slash_menu_and_keeps_the_text(app, inp):
    start(app, '')
    inp.type('/ta')
    menu(app)
    inp.key('esc')
    wait_until(lambda: not menu_open(app), what='the menu to close')
    inp.key('enter')
    assert_saved(app, "paragraph('/ta') paragraph()")


def test_U11_enter_on_an_empty_line_in_an_expand_stays_in_it(app, inp):
    note = start(app, f'{EXPAND_OPEN}T\nfirst\n{EXPAND_END}')
    note.click_text(60, 31)          # "first"
    inp.key('end')
    inp.key('enter')
    inp.key('enter')
    inp.type('third')
    assert_saved(app, "expand(expand_title('T') paragraph('first') paragraph() paragraph('third')) paragraph()")


def test_U12_enter_on_an_empty_line_in_code_stays_in_the_code(app, inp):
    note = start(app, 'ls', code_ranges=[[0, 2]])
    note.click_text(30, 8)
    inp.key('end')
    inp.key('enter')
    inp.key('enter')
    inp.type('pwd')
    assert_saved(app, "code_block('ls\\n\\npwd') paragraph()")


def test_U13_down_goes_below_a_code_block_at_the_end(app, inp):
    note = start(app, 'ls', code_ranges=[[0, 2]])
    note.click_text(30, 8)
    inp.key('down')
    inp.type('after')
    assert_saved(app, "code_block('ls') paragraph('after')")


def expand_with_table(app):
    rows = [[{'text': 'k'}], [{'text': 'v'}]]
    note = start(app, f'{EXPAND_OPEN}T\n\ufffc\n{EXPAND_END}', tables=[{'offset': 4, 'rows': rows}])
    note.click_text(60, 0)           # the title
    inp = app.inp
    inp.key('down')
    inp.key('down')                  # the last row
    inp.key('end')
    return note


def test_U14_right_at_a_tables_end_in_an_expand_writes_below_the_table_in_it(app, inp):
    expand_with_table(app)
    inp.key('right')
    inp.type('x')
    assert_saved(app, "expand(expand_title('T') table(table_row(table_header(paragraph('k'))) "
                      "table_row(table_cell(paragraph('v')))) paragraph('x')) paragraph()")


def test_U18_down_from_a_tables_last_row_in_an_expand_leaves_the_expand(app, inp):
    expand_with_table(app)
    inp.key('down')
    inp.type('y')
    assert_saved(app, "expand(expand_title('T') table(table_row(table_header(paragraph('k'))) "
                      "table_row(table_cell(paragraph('v'))))) paragraph('y')")


def test_U15_ctrl_v_pastes_an_image_from_the_clipboard(app, inp):
    start(app, 'see ')
    pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 40, 30)
    pixbuf.fill(0x3366ccff)
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    clipboard.set_image(pixbuf)
    clipboard.store()
    pump()
    inp.key('ctrl+v')

    def image():
        pump()
        try:
            content = saved_note(app)['doc']['content'][0].get('content', [])
        except Exception:
            return None
        return next((n for n in content if n['type'] == 'image'), None)
    node = wait_until(image, what='an image in the note')
    assert os.path.isfile(os.path.join(app.conf, 'images', node['attrs']['file']))


def test_U16_find_in_all_notes_finds_a_hidden_note_and_shows_it(app, inp):
    app.write_notes([
        {'id': 'test', 'title': 'test', 'text': 'here', 'x': 100, 'y': 80, 'w': 420, 'h': 360},
        {'id': 'k8s', 'title': 'k8s', 'text': 'kubectl rollout restart deploy/api', 'hidden': True,
         'x': 600, 'y': 80, 'w': 300, 'h': 300}])
    app.start()
    note = WebNote(app, app.note('test').frame)
    note.click_text(10, 8)
    inp.key('ctrl+f')
    inp.key('alt+a')                 # All notes
    inp.type('restart')
    settle(0.4)
    inp.key('enter')
    app.note('k8s')
    wait_until(lambda: saved_note(app, 'k8s').get('hidden') is False, what='k8s shown')


def test_U17_the_note_menu_holds_nothing_a_title_bar_button_does(app, inp):
    note = start(app, 'hello')
    note.press('Note menu')
    names = [i.get_name() for i in menu_items(app)]
    for label in ('Collapse', 'Always on top', 'Hide note'):
        assert not any(n.startswith(label) for n in names), names


def test_U19_two_slashes_where_a_word_starts_type_todays_date(app, inp):
    start(app, 'log ')
    inp.type('//')
    today = datetime.date.today().isoformat()
    inp.type(' done')
    assert_saved(app, f"paragraph('log {today} done')")


def test_U20_two_slashes_after_other_text_stay_as_typed(app, inp):
    start(app, '')
    inp.type('https://example.com')
    assert_saved(app, "paragraph('https://example.com')")


def test_U21_finds_toggles_stay_as_last_set(app, inp):
    import json
    note = start(app, 'Error error')
    inp.key('ctrl+f')
    inp.key('alt+c')                 # match case
    inp.key('alt+a')                 # all notes
    inp.key('esc')
    settle(0.3)
    inp.key('ctrl+f')
    inp.type('Error')
    settle(0.5)
    from tests.e2e.driver import find_all, name, role
    results = [a for a in find_all(note.frame, lambda a: role(a) in ('list item', 'option'), limit=40)]
    assert len(results) == 1, [name(a) for a in results]
    settings = json.load(open(os.path.join(app.conf, 'settings.json')))
    assert settings['find'].get('caseSensitive') and settings['find'].get('all'), settings
    assert not settings['find'].get('regex'), settings


def test_U22_a_drag_up_over_a_table_selects_everything_it_passes(app, inp):
    rows = [[{'text': 'k'}, {'text': 'v'}], [{'text': 'a'}, {'text': 'b'}]]
    text = 'example text\n\n￼\n\nempty line'
    note = start(app, text, tables=[{'offset': 14, 'rows': rows}])
    from tests.e2e.web import text_holding
    from tests.e2e.driver import Atspi
    acc, at = text_holding(note, 'empty line')
    end = Atspi.Text.get_character_extents(acc, at + 9, Atspi.CoordType.SCREEN)
    acc2, at2 = text_holding(note, 'example text')
    first = Atspi.Text.get_character_extents(acc2, at2, Atspi.CoordType.SCREEN)
    inp.drag((end.x + end.width, end.y + end.height // 2), (first.x + 1, first.y + first.height // 2), steps=16)
    settle(0.3)
    inp.type('X')
    assert_saved(app, "paragraph('X')")


def test_U23_a_drag_from_below_the_text_selects_up_to_where_it_ends(app, inp):
    note = start(app, 'example text\n\nempty line')
    from tests.e2e.web import text_holding
    from tests.e2e.driver import Atspi
    acc, at = text_holding(note, 'example text')
    first = Atspi.Text.get_character_extents(acc, at, Atspi.CoordType.SCREEN)
    x, y, w, h = note.box
    inp.drag((x + w // 2, y + h - 60), (first.x + 1, first.y + first.height // 2), steps=16)
    settle(0.3)
    inp.type('X')
    assert_saved(app, "paragraph('X')")


def test_U24_a_drag_from_the_empty_line_below_a_table_up_over_it_selects_it_all(app, inp):
    rows = [[{'text': 'k'}, {'text': 'v'}], [{'text': 'a'}, {'text': 'b'}]]
    note = start(app, 'example text\n\n￼\n', tables=[{'offset': 14, 'rows': rows}])
    from tests.e2e.web import text_holding
    from tests.e2e.driver import Atspi
    acc, at = text_holding(note, 'example text')
    first = Atspi.Text.get_character_extents(acc, at, Atspi.CoordType.SCREEN)
    acc2, at2 = text_holding(note, 'b')
    last_cell = Atspi.Text.get_character_extents(acc2, at2, Atspi.CoordType.SCREEN)
    below = last_cell.y + last_cell.height + 22          # the empty line after the table
    inp.drag((first.x + 4, below), (first.x + 1, first.y + first.height // 2), steps=20)
    settle(0.3)
    inp.type('X')
    assert_saved(app, "paragraph('X')")
